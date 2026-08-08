# llm/qwen_client.py

import requests
from typing import Optional, List
from langchain_core.language_models.llms import LLM


class LocalQwen(LLM):
    model_name: str = "qwen2.5:7b"
    url: str = (
        "http://localhost:11434/api/chat"
    )
    temperature: float = 0.0


    @property
    def _llm_type(self):
        return "local_qwen"


    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]]=None,
        **kwargs
    ):

        payload = {
            "model":self.model_name,
            "messages":[
                {
                    "role":"user",
                    "content":prompt
                }
            ],
            "stream":False,
            "format": "json",
            "options":{
                "temperature":
                    self.temperature
            }

        }
        response=requests.post(
            self.url,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return (
            response
            .json()
            ["message"]
            ["content"]
        )
