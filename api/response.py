import os
import json
import logging
from supabase import create_client, Client
import fasttext
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SUPABASE_URL = "https://uafyaolgsepatpkgxrha.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVhZnlhb2xnc2VwYXRwa2d4cmhhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY5MTYwNDYsImV4cCI6MjA2MjQ5MjA0Nn0.heNSA8V86WSBXWWQSqzpLYS5p-v5TyKhSo-PB8XnT60"
MYMEMORY_API_KEY = "803876a9e4f30ab69842"
MYMEMORY_API_URL = "https://api.mymemory.translated.net/get"

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    raise

def load_language_detector():
    """Load the fasttext language detection model with extensive debugging."""
    try:
        # Get the directory of the current script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Base directory: {base_dir}")
        
        # Check possible locations for the model file
        possible_paths = [
            os.path.join(base_dir, 'lid.176.ftz'),
            os.path.join(base_dir, '.pythonlibs', 'lid.176.ftz'),
            os.path.join(base_dir, 'lib', 'python3.11', 'site-packages', 'lid.176.ftz'),
            '/tmp/lid.176.ftz',
            'lid.176.ftz'
        ]
        
        logger.info(f"Searching for model in paths: {possible_paths}")
        
        for model_path in possible_paths:
            logger.info(f"Checking path: {model_path}")
            if os.path.exists(model_path):
                logger.info(f"Found model at: {model_path}")
                logger.info(f"File size: {os.path.getsize(model_path)} bytes")
                logger.info(f"File permissions: {oct(os.stat(model_path).st_mode)[-3:]}")
                return fasttext.load_model(model_path)
        
        raise FileNotFoundError(f"Model not found in any of: {possible_paths}")
    except Exception as e:
        logger.error(f"Error loading language detector: {str(e)}")
        raise RuntimeError(f"Failed to load language detection model: {str(e)}")

# Load the language detector with fallback
try:
    language_detector = load_language_detector()
    logger.info("Language detector loaded successfully")
except Exception as e:
    logger.error(f"Failed to load language detector: {str(e)}")
    language_detector = None

def detect_language(text):
    """Detect language with fallback to English."""
    if not text or not isinstance(text, str):
        logger.warning("Empty or invalid text provided for language detection")
        return 'en'
    
    if language_detector is None:
        logger.warning("Language detector not available, defaulting to English")
        return 'en'
    
    try:
        predictions = language_detector.predict(text, k=1)
        lang_code = predictions[0][0].replace('__label__', '')
        logger.info(f"Detected language: {lang_code} for text: {text[:50]}...")
        return lang_code
    except Exception as e:
        logger.error(f"Language detection failed: {str(e)}")
        return 'en'

def translate_text(text, source_lang, target_lang='en'):
    """Translate text with robust error handling."""
    if not text:
        logger.warning("Empty text provided for translation")
        return text
    
    params = {
        'q': text,
        'langpair': f"{source_lang}|{target_lang}",
        'key': MYMEMORY_API_KEY
    }
    
    try:
        logger.info(f"Attempting translation for: {text[:50]}...")
        response = requests.get(MYMORY_API_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        translated = data.get('responseData', {}).get('translatedText', text)
        logger.info(f"Translation successful: {text[:20]}... -> {translated[:20]}...")
        return translated
    except requests.exceptions.RequestException as e:
        logger.error(f"Translation API request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
    
    return text

def get_message_and_translate():
    """Main function with comprehensive error handling."""
    try:
        logger.info("Attempting to retrieve message from database")
        response = supabase.table('messages').select('message').limit(1).execute()
        
        if not response.data:
            logger.warning("No messages found in database")
            return {"messages": [{"response": "No messages found", "original_language": "en"}]}
        
        original_message = response.data[0].get('message', '')
        if not original_message:
            logger.warning("Empty message retrieved from database")
            return {"messages": [{"response": "Empty message", "original_language": "en"}]}
        
        logger.info(f"Retrieved message: {original_message[:50]}...")
        
        lang_code = detect_language(original_message)
        translated_text = translate_text(original_message, lang_code)
        
        result = {
            "messages": [{
                "response": translated_text,
                "original_language": lang_code
            }]
        }
        logger.info(f"Successfully processed message: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in get_message_and_translate: {str(e)}", exc_info=True)
        return {
            "messages": [{
                "response": f"Error processing request: {str(e)}",
                "original_language": "en"
            }]
        }

# Vercel-compatible handler
def app(request):
    try:
        logger.info("Vercel handler invoked")
        result = get_message_and_translate()
        response = json.dumps(result)
        logger.info(f"Returning response: {response[:100]}...")
        return response
    except Exception as e:
        logger.error(f"Error in Vercel handler: {str(e)}", exc_info=True)
        return json.dumps({
            "messages": [{
                "response": f"Server error: {str(e)}",
                "original_language": "en"
            }]
        })

# AWS Lambda handler
def lambda_handler(event, context):
    try:
        logger.info("Lambda handler invoked")
        result = get_message_and_translate()
        return {
            'statusCode': 200,
            'body': json.dumps(result),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
    except Exception as e:
        logger.error(f"Error in Lambda handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "messages": [{
                    "response": f"Server error: {str(e)}",
                    "original_language": "en"
                }]
            }),
            'headers': {
                'Content-Type': 'application/json'
            }
        }

if __name__ == "__main__":
    # Test the function locally
    print("Running local test...")
    result = get_message_and_translate()
    print(json.dumps(result, indent=2))
