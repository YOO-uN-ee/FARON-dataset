import torch
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler
from diffusers.utils import load_image

# 1. Load the specific ControlNet model (Segmentation)
# This model knows that "Blocky shapes" = Buildings
controlnet = ControlNetModel.from_pretrained(
    "lllyasviel/sd-controlnet-seg", torch_dtype=torch.float16
)

# 2. Load the main Stable Diffusion Model (The "Artist")
# You can swap this for "realisticVision" or other map-specific models
pipe = StableDiffusionControlNetPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5", controlnet=controlnet, torch_dtype=torch.float16
)

# Optimize for speed
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
pipe.enable_model_cpu_offload()

# 3. Load your mask from Step 1
image = load_image("map_shapes.png")

# 4. Generate the Map
# The 'image' argument forces the AI to stick to your polygon layout
result = pipe(
    "Satellite view of a city, realistic 4k, roads, buildings, top down view",
    image=image,
    num_inference_steps=20,
    guidance_scale=7.5,
).images[0]

result.save("./generated_realistic_map.png")