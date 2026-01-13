from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig


@dataclass(frozen=True)
class VertexLLM:
    project_id: str
    region: str
    model_name: str

    def __post_init__(self) -> None:
        vertexai.init(project=self.project_id, location=self.region)

    def generate_json(
        self,
        system_instruction: str,
        user_input: str,
        *,
        temperature: float = 0.0,
        max_output_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """
        Calls Gemini on Vertex AI and returns parsed JSON.
        Raises ValueError if the model output is not valid JSON.
        """
        model = GenerativeModel(
            self.model_name,
            system_instruction=system_instruction,
        )

        resp = model.generate_content(
            user_input,
            generation_config=GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
            ),
        )

        text = (resp.text or "").strip()
        if not text:
            raise ValueError("Empty model response")

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Helpful debug payload (keep short)
            snippet = text[:800]
            raise ValueError(f"Model output is not valid JSON. Snippet: {snippet}") from e
