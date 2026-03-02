from typing import Any

import torch

# Monkey-patch for optimum compatibility with new transformers
import transformers.utils
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM

if not hasattr(transformers.utils, "is_tf_available"):
    transformers.utils.is_tf_available = lambda: False

from airllm import AutoModel
from transformers import AutoTokenizer


class AirLLMWrapper(LLM):
    """AirLLM Wrapper for LangChain for layer-wise local inference."""

    model_id: str
    model: Any = None
    tokenizer: Any = None

    def __init__(self, model_id: str, **kwargs):
        super().__init__(model_id=model_id, **kwargs)
        import os

        hf_token = os.environ.get("HF_TOKEN", os.environ.get("HUGGING_FACE_HUB_TOKEN"))
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)
        self.model = AutoModel.from_pretrained(model_id, kwargs={"token": hf_token})

    @property
    def _llm_type(self) -> str:
        return "airllm"

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> str:
        # Route execution to Apple's Metal Performance Shaders (mps) if available, otherwise cpu
        device = "mps" if torch.backends.mps.is_available() else "cpu"

        # Tokenize the incoming prompt
        inputs = self.tokenizer(prompt, return_tensors="pt")
        input_ids = inputs.input_ids.to(device)

        # Execute self.model.generate() to process the layers
        max_new_tokens = kwargs.get("max_new_tokens", 512)
        outputs = self.model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            return_dict_in_generate=True,
        )

        # Decode the output
        if hasattr(outputs, "sequences"):
            output_sequence = outputs.sequences[0]
        else:
            output_sequence = outputs[0]

        generated_text = self.tokenizer.decode(
            output_sequence, skip_special_tokens=True
        )

        # Strip the original prompt from the generated text before returning it
        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt) :]

        return generated_text.strip()
