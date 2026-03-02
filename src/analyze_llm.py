import os
import json
import logging
import google.generativeai as genai
from typing import Dict, Any

from src.utils import get_utc_timestamp, write_json
from src.schema import LLM_OUTPUT_SCHEMA

logger = logging.getLogger(__name__)

def analyze_portfolio(snapshot: Dict[str, Any], out_dir: str = "out") -> Dict[str, Any]:
    """
    Sends the normalized snapshot to Gemini and requires the output strictly
    as JSON matching our defined output schema.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Environment variable GOOGLE_API_KEY must be set.")
        
    genai.configure(api_key=api_key)
    
    # We use gemini-1.5-flash for speed, cost-effectiveness, and excellent JSON adherence.
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an expert financial analyst. Please analyze the following portfolio snapshot.
    
    <Portfolio_Snapshot>
    {json.dumps(snapshot, indent=2)}
    </Portfolio_Snapshot>
    
    You must output your response STRICTLY as JSON matching the following JSON Schema:
    {json.dumps(LLM_OUTPUT_SCHEMA, indent=2)}
    
    Return ONLY a valid, parsable JSON object. Do not include markdown code block formatting like ```json or ```.
    """
    
    logger.info("Sending portfolio snapshot to Gemini for analysis...")
    
    # Depending on the installed version, response_mime_type enforces JSON return payload.
    # Fallbacks are configured in prompt formulation for safety.
    generation_config = genai.types.GenerationConfig(
        response_mime_type="application/json",
        temperature=0.2 # Lower temperature for analytical deterministic results
    )
    
    response = model.generate_content(
        prompt,
        generation_config=generation_config
    )
    
    raw_text = response.text.strip()
    
    # Defensive cleanup in case the LLM ignores instructions and wraps in markdown
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
        
    raw_text = raw_text.strip()
    
    try:
        decisions: Dict[str, Any] = json.loads(raw_text)
        logger.info("Successfully parsed Gemini response as JSON.")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode Gemini output as JSON: {e}")
        logger.debug(f"Raw output text was: {raw_text}")
        raise
        
    timestamp = get_utc_timestamp()
    filepath = os.path.join(out_dir, f"decisions_{timestamp}.json")
    write_json(decisions, filepath)
    
    return decisions
