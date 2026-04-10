from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.tools.base import BaseTool, ToolResult


class ImageGenerationTool(BaseTool):
    name = "image"
    description = "Generates or edits images with a local Stable Diffusion pipeline."

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._txt2img = None
        self._img2img = None

    def _load_pipeline(self) -> None:
        if self._txt2img is not None:
            return
        if not self.settings.stable_diffusion_model_path:
            raise RuntimeError("Set FRIDAY_STABLE_DIFFUSION_MODEL_PATH to a local model directory first.")
        try:
            from diffusers import StableDiffusionImg2ImgPipeline, StableDiffusionPipeline
        except ImportError as exc:
            raise RuntimeError("Vision dependencies are not installed. Install the vision extra.") from exc

        model_path = self.settings.stable_diffusion_model_path
        self._txt2img = StableDiffusionPipeline.from_pretrained(model_path)
        self._img2img = StableDiffusionImg2ImgPipeline.from_pretrained(model_path)

    def _generate_sync(
        self,
        prompt: str,
        negative_prompt: str | None,
        output_path: Path,
        steps: int,
        guidance_scale: float,
        batch_size: int,
        init_image_path: Path | None = None,
    ) -> list[str]:
        self._load_pipeline()
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Pillow is required for image generation.") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        saved_paths: list[str] = []

        if init_image_path:
            init_image = Image.open(init_image_path).convert("RGB")
            result = self._img2img(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=init_image,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                num_images_per_prompt=batch_size,
            )
        else:
            result = self._txt2img(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                num_images_per_prompt=batch_size,
            )

        for index, image in enumerate(result.images):
            final_path = output_path.with_name(f"{output_path.stem}-{index}{output_path.suffix}")
            image.save(final_path)
            saved_paths.append(str(final_path))
        return saved_paths

    async def execute(self, **kwargs: Any) -> ToolResult:
        prompt = kwargs.get("prompt")
        if not prompt:
            return ToolResult(success=False, output="Missing 'prompt' argument.")

        output_path = Path(kwargs.get("output_path", self.settings.generated_dir / "friday-image.png"))
        init_image = kwargs.get("init_image_path")
        saved_paths = await asyncio.to_thread(
            self._generate_sync,
            prompt,
            kwargs.get("negative_prompt"),
            output_path,
            int(kwargs.get("steps", 30)),
            float(kwargs.get("guidance_scale", 7.5)),
            int(kwargs.get("batch_size", 1)),
            Path(init_image) if init_image else None,
        )
        return ToolResult(success=True, output="\n".join(saved_paths), metadata={"paths": saved_paths})
