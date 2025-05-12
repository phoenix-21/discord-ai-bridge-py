import sys
from pathlib import Path
import logging
from fastapi import FastAPI, HTTPException
import httpx
from typing import List
from collections import Counter

# Add .pythonlibs to Python path
python_libs_path = Path(__file__).parent / ".pythonlibs"
if python_libs_path.exists():
    sys.path.insert(0, str(python_libs_path))

try:
    from langdetect import detect, DetectorFactory, LangDetectException
    DETECTOR_AVAILABLE = True
except ImportError as e:
    logging.error(f"Langdetect import failed: {e}")
    DETECTOR_AVAILABLE = False
    
    # Enhanced fallback detector with German priority
    def detect(text: str) -> str:
        """Fallback detector with special handling for German"""
        german_indicators = [
            'ich', 'du', 'und', 'die', 'der', 'das', 
            'bin', 'so', 'aufgeregt', 'nicht', 'wir'
        ]
        text_lower = text.lower()
        
        # Check for strong German indicators first
        if any(word in text_lower for word in german_indicators):
            return 'de'
            
        # Fallback to simple English detection
        english_words = ['the', 'be', 'to', 'of', 'and']
        return 'en' if any(word in text_lower for word in english_words) else 'de'
    
    DetectorFactory = type('DetectorFactory', (), {'seed': lambda self, x: None})

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# For more consistent language detection
DetectorFactory.seed = 0

# Supabase configuration
SUPABASE_URL = "https://uafyaolgsepatpkgxrha.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVhZnlhb2xnc2VwYXRwa2d4cmhhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY5MTYwNDYsImV4cCI6MjA2MjQ5MjA0Nn0.heNSA8V86WSBXWWQSqzpLYS5p-v5TyKhSo-PB8XnT60"

# MyMemory API configuration
MYMEMORY_API_KEY = "803876a9e4f30ab69842"
MYMEMORY_API_URL = "https://api.mymemory.translated.net/get"

async def translate_text(text: str, target_lang: str = "en") -> str:
    """Translate text using MyMemory API with enhanced German detection"""
    try:
        if not text.strip():
            raise ValueError("Empty text provided for translation")
        
        # Enhanced German detection
        try:
            if DETECTOR_AVAILABLE:
                # First get initial detection
                source_lang = detect(text)
                
                # Special handling for Somali/German confusion
                if source_lang == 'so':
                    german_indicators = [
                        'ich', 'du', 'und', 'die', 'der', 'das',
                        'bin', 'so', 'aufgeregt', 'nicht', 'wir'
                    ]
                    if any(word in text.lower() for word in german_indicators):
                        source_lang = 'de'
                        logger.info(f"Overriding Somali detection to German for: {text[:50]}...")
            else:
                # Use our enhanced fallback detector
                source_lang = detect(text)
            
            logger.info(f"Final detected language: {source_lang} for text: {text[:50]}...")
            
        except Exception as e:
            logger.warning(f"Language detection failed, defaulting to 'en': {str(e)}")
            source_lang = "en"
        
        # Validate language codes
        source_lang = source_lang[:2] if len(source_lang) > 2 else source_lang
        target_lang = target_lang[:2] if len(target_lang) > 2 else target_lang
            
        async with httpx.AsyncClient() as client:
            params = {
                "q": text,
                "langpair": f"{source_lang}|{target_lang}",
                "key": MYMEMORY_API_KEY
            }
            logger.info(f"Sending translation request with params: {params}")
            
            response = await client.get(MYMEMORY_API_URL, params=params)
            logger.info(f"Translation API response status: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            logger.info(f"Translation API response data: {data}")
            
            if data.get("responseStatus") != 200:
                error_msg = data.get("responseDetails", "Translation failed")
                logger.error(f"Translation failed: {error_msg}")
                raise HTTPException(status_code=400, detail=error_msg)
            
            translated_text = data["responseData"]["translatedText"]
            logger.info(f"Successfully translated: {text[:50]}... -> {translated_text[:50]}...")
            return translated_text
            
    except httpx.HTTPStatusError as e:
        logger.error(f"MyMemory API HTTP error: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Translation service error: {str(e)}")
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Translation error: {str(e)}")


@app.get("/api/response")
async def get_response():
    """Endpoint that returns translated messages in the requested format"""
    try:
        # First check if we can get messages from Supabase
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/messages",
                headers={
                    "apikey": SUPABASE_API_KEY,
                    "Authorization": f"Bearer {SUPABASE_API_KEY}",
                    "Content-Type": "application/json"
                },
                params={
                    "select": "message",
                    "order": "created_at.desc",
                    "limit": "1"
                }
            )
            response.raise_for_status()
            messages = response.json()
            logger.info(f"Retrieved messages from Supabase: {messages}")

        if not messages:
            logger.info("No messages found in database")
            return {"messages": [{"response": "No messages found", "original_language": "unknown"}]}

        # Process messages
        results = []
        for message in messages:
            text = message.get("message", "")
            if text.strip():
                try:
                    translated = await translate_text(text)
                    # Get detected language for original_language field
                    try:
                        if DETECTOR_AVAILABLE:
                            source_lang = detect(text)
                            if len(source_lang) > 2:
                                source_lang = source_lang[:2]
                        else:
                            source_lang = "unknown"
                    except:
                        source_lang = "unknown"
                        
                    results.append({
                        "response": translated,
                        "original_language": source_lang
                    })
                except Exception as e:
                    logger.error(f"Failed to translate message: {str(e)}")
                    results.append({
                        "response": f"[Translation failed] {text}",
                        "original_language": "unknown"
                    })
            else:
                results.append({
                    "response": "[Empty message]",
                    "original_language": "unknown"
                })

        return {"messages": results}

    except httpx.HTTPStatusError as e:
        logger.error(f"Supabase API error: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Database service error: {str(e)}")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
