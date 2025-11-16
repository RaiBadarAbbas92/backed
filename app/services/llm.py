"""Wrapper around Google Gemini Pro API."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, Optional

import google.generativeai as genai

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Convenience wrapper for Gemini Pro completions."""

    def __init__(self, api_key: str, model: str) -> None:
        genai.configure(api_key=api_key)
        self._model = model
        # Remove 'models/' prefix if present - the SDK handles it
        clean_model = model.replace("models/", "") if model.startswith("models/") else model
        logger.info("Initializing Gemini client with model: %s", clean_model)
        try:
            self._client = genai.GenerativeModel(model_name=clean_model)
            logger.info("Successfully initialized Gemini model: %s", clean_model)
        except Exception as e:
            logger.error("Failed to initialize Gemini model '%s': %s", clean_model, e)
            # Try with common fallback models
            fallback_models = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
            for fallback in fallback_models:
                try:
                    logger.info("Trying fallback model: %s", fallback)
                    self._client = genai.GenerativeModel(model_name=fallback)
                    self._model = fallback
                    logger.info("Successfully initialized with fallback model: %s", fallback)
                    break
                except Exception:
                    continue
            else:
                raise ValueError(f"Could not initialize any Gemini model. Original error: {e}")

    def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        top_p: float = 0.8,
        top_k: int = 32,
        max_output_tokens: int = 300,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a response from Gemini Pro."""
        generation_config = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_output_tokens": max_output_tokens,
        }

        # Try to use safety settings, but handle errors gracefully
        safety_settings = None
        try:
            # Try using enum format first (newer API versions)
            if hasattr(genai, 'types') and hasattr(genai.types, 'HarmCategory'):
                safety_settings = [
                    {
                        "category": genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                    {
                        "category": genai.types.HarmCategory.HARM_CATEGORY_SELF_HARM,
                        "threshold": genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                    {
                        "category": genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                    {
                        "category": genai.types.HarmCategory.HARM_CATEGORY_SEXUAL,
                        "threshold": genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                ]
        except (AttributeError, KeyError, TypeError) as e:
            logger.warning("Could not configure safety settings with enums: %s. Will skip safety settings.", e)
            safety_settings = None

        response = None
        try:
            # Call generate_content with or without safety_settings
            if safety_settings:
                response = self._client.generate_content(
                    prompt, generation_config=generation_config, safety_settings=safety_settings
                )
            else:
                # Call without safety_settings if they cause issues
                response = self._client.generate_content(
                    prompt, generation_config=generation_config
                )

            if response is None:
                logger.error("Gemini API returned None response")
                return "I'm sorry, I'm unable to retrieve the requested information right now."

            # Method 1: Use the .text property (recommended by Google SDK)
            # This is the safest and most direct way to get text from Gemini responses
            try:
                if hasattr(response, 'text'):
                    text = response.text
                    if text and isinstance(text, str) and text.strip():
                        logger.debug("Successfully extracted text using response.text property")
                        return text.strip()
            except (KeyError, AttributeError, IndexError, TypeError) as e:
                logger.warning("Failed to access response.text property: %s", e)
            except Exception as e:
                logger.warning("Unexpected error accessing response.text: %s (type: %s)", e, type(e).__name__)

            # Method 2: Fallback to manual extraction
            if not response.candidates:
                logger.warning("Gemini returned no candidates. Response: %s", response)
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    logger.warning("Prompt feedback: %s", response.prompt_feedback)
                return "I'm sorry, I'm unable to retrieve the requested information right now."

            # Safely extract text content from response
            candidate = response.candidates[0]
            if not hasattr(candidate, 'content') or not candidate.content:
                logger.warning("Candidate has no content. Candidate: %s", candidate)
                return "I'm sorry, I'm unable to retrieve the requested information right now."

            content_obj = candidate.content
            if not hasattr(content_obj, 'parts') or not content_obj.parts:
                logger.warning("Content has no parts. Content: %s", content_obj)
                return "I'm sorry, I'm unable to retrieve the requested information right now."

            # Try to get text from the first part
            first_part = content_obj.parts[0]
            
            # Try attribute access
            if hasattr(first_part, 'text'):
                text = first_part.text
                if text:
                    return text.strip()
            
            logger.warning("First part has no accessible text. Part type: %s, Part: %s", type(first_part), first_part)
            return "I'm sorry, I'm unable to retrieve the requested information right now."
        except KeyError as exc:
            # Handle KeyError specifically - likely accessing response structure incorrectly
            response_info = f"Response: {response}" if response is not None else "Response not yet created"
            logger.exception("KeyError accessing Gemini response structure: %s. %s", exc, response_info)
            return (
                f"I'm experiencing technical difficulties parsing the AI response "
                f"(KeyError: {exc}). Please try again or contact support."
            )
        except ValueError as exc:
            # API key or configuration errors
            error_msg = str(exc)
            logger.error("Gemini API configuration error: %s", error_msg)
            if "API key" in error_msg.lower() or "api_key" in error_msg.lower():
                return (
                    "Configuration error: Gemini API key is missing or invalid. "
                    "Please check your GEMINI_API_KEY environment variable."
                )
            return f"Configuration error: {error_msg}"
        except Exception as exc:  # pylint: disable=broad-except
            error_type = type(exc).__name__
            error_msg = str(exc)
            logger.exception("Gemini call failed [%s]: %s", error_type, error_msg)
            
            # Handle rate limit / quota exceeded errors
            if ("ResourceExhausted" in error_type or 
                "429" in error_msg or 
                "quota" in error_msg.lower() or 
                "rate limit" in error_msg.lower() or
                "exceeded" in error_msg.lower() and "quota" in error_msg.lower()):
                # Extract retry delay if available
                retry_seconds = None
                if "retry in" in error_msg.lower():
                    try:
                        import re
                        match = re.search(r"retry in ([\d.]+)s", error_msg.lower())
                        if match:
                            retry_seconds = int(float(match.group(1)))
                    except Exception:
                        pass
                
                logger.warning("Rate limit exceeded for model '%s'. Error: %s", self._model, error_msg[:200])
                if retry_seconds:
                    return (
                        f"I'm currently experiencing high demand. Please wait about {retry_seconds} seconds and try again. "
                        f"This is due to API rate limits on the free tier (2 requests per minute)."
                    )
                else:
                    return (
                        "I'm currently experiencing high demand. Please wait a moment and try again. "
                        "This is due to API rate limits on the free tier (2 requests per minute)."
                    )
            
            # Handle NotFound error in error message (check error type and message)
            if ("NotFound" in error_type or 
                "not found" in error_msg.lower() or 
                "404" in error_msg or 
                "NotFoundError" in error_type or
                "does not exist" in error_msg.lower() or
                "model" in error_msg.lower() and "not found" in error_msg.lower()):
                logger.error("Model '%s' not found. Available models: gemini-pro, gemini-1.5-flash", self._model)
                return (
                    f"Configuration error: The AI model '{self._model}' was not found. "
                    f"Please check your API key and ensure you have access to Gemini models. "
                    f"Try setting GEMINI_MODEL=gemini-pro in your environment."
                )
            
            return (
                f"I'm experiencing technical difficulties reaching our knowledge services "
                f"(Error: {error_type}: {error_msg[:200]}). Let me connect you with a human specialist."
            )


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Return a cached Gemini client instance."""
    settings = get_settings()
    return GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)



