from typing import List, Dict, Any, Tuple
from app.core.config import settings

def _fmt(docs):
    return "\n\n".join(f"[{i+1}] {d.get('filename','?')}:\n{d['transcription']}"
                       for i, d in enumerate(docs))

def generate_answer(question: str, docs: List[Dict[str, Any]]) -> Tuple[str, str]:
    provider = settings.llm_provider.lower()
    try:
        if provider == "gemini" and settings.gemini_api_key:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            r = genai.GenerativeModel("gemini-1.5-flash").generate_content(
                f"Transkrypcje EBC:\n{_fmt(docs)}\n\nPytanie: {question}\nOdpowiedz zwiezle.")
            return r.text, "gemini-1.5-flash"
        elif provider == "openai" and settings.openai_api_key:
            from openai import OpenAI
            r = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role":"user","content":f"Transkrypcje:\n{_fmt(docs)}\n\nPytanie: {question}"}])
            return r.choices[0].message.content, "gpt-3.5-turbo"
        else:
            return f"[local] Na podstawie {len(docs)} transkrypcji:\n\n{_fmt(docs)[:800]}", "local"
    except Exception as e:
        return f"Blad LLM: {e}", "local-fallback"
