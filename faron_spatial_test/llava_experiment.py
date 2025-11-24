import torch
from transformers import LlavaNextProcessor, LlavaNextForConditionalGeneration
from PIL import Image
import faron_spatial_test.topology_generator as topo # Imports the file created above

# --- 1. Model Setup ---
print("Loading LLaVA Model...")
# Using LLaVA-NeXT (v1.6) or 1.5. Adjust model_id as needed for your VRAM.
# standard 1.5: "llava-hf/llava-1.5-7b-hf" 
# mistral-based: "llava-hf/llava-v1.6-mistral-7b-hf"
model_id = "llava-hf/llava-1.5-7b-hf" 

processor = LlavaNextProcessor.from_pretrained(model_id)
model = LlavaNextForConditionalGeneration.from_pretrained(
    model_id, 
    torch_dtype=torch.float16, 
    low_cpu_mem_usage=True,
    device_map="auto" # Requires CUDA
)
print("Model Loaded.")

# --- 2. Prompt Templates ---

def run_inference(image, text_prompt):
    """Generic inference helper for LLaVA."""
    # LLaVA 1.5 prompt format: "USER: <image>\n<prompt>\nASSISTANT:"
    prompt = f"USER: <image>\n{text_prompt}\nASSISTANT:"
    
    inputs = processor(text=prompt, images=image, return_tensors="pt").to(model.device)
    
    # Generate
    output = model.generate(**inputs, max_new_tokens=100)
    response = processor.decode(output[0], skip_special_tokens=True)
    
    # Extract only the assistant's reply
    try:
        return response.split("ASSISTANT:")[1].strip()
    except:
        return response

# --- 3. Experimental Conditions ---

def run_condition_a_vision(experiment, shape_a, shape_b):
    """
    Condition A: Vision Only.
    The model sees the raw image and must deduce the relationship.
    """
    print("Running Condition A (Vision Only)...")
    image = experiment.render_to_pil(shape_a, shape_b, visual_cues=False)
    
    prompt = (
        "Analyze the spatial relationship between the Red Object and the Blue Object. "
        "Choose exactly one of the following: Disconnected, Touching, Overlapping, "
        "Red is Inside Blue, or Blue is Inside Red."
    )
    
    return run_inference(image, prompt)


def run_condition_b_coordinates(shape_a, shape_b):
    """
    Condition B: Text/Coordinates Only.
    We pass a blank image (required by pipeline) but provide precise coordinates.
    """
    print("Running Condition B (Coordinates)...")
    
    # Create a blank dummy image
    dummy_image = Image.new('RGB', (224, 224), color='black')
    
    # Extract Coordinates (WKT or Bounds)
    # Using Bounds [minx, miny, maxx, maxy] is usually easier for LLMs than full WKT
    bounds_a = [round(x, 2) for x in shape_a.bounds]
    bounds_b = [round(x, 2) for x in shape_b.bounds]
    
    prompt = (
        f"I am providing bounding box coordinates for two objects.\n"
        f"Object A (Red): {bounds_a}\n"
        f"Object B (Blue): {bounds_b}\n"
        "Based on these numbers, what is the topological relationship? "
        "Are they Disconnected, Touching, Overlapping, or one Inside the other?"
    )
    
    return run_inference(dummy_image, prompt)


def run_condition_c_visual_cues(experiment, shape_a, shape_b):
    """
    Condition C: Visual Prompting.
    The model sees the image with explicit bounding boxes drawn on it.
    """
    print("Running Condition C (Visual Cues)...")
    
    # Render with visual_cues=True (Dashed boxes)
    image = experiment.render_to_pil(shape_a, shape_b, visual_cues=True)
    
    prompt = (
        "I have drawn dashed bounding boxes around the Red Object and the Blue Object to help you. "
        "Look at the boundaries indicated by the dashed lines. "
        "What is the topological relationship? (Disconnected, Touching, Overlapping, Inside)"
    )
    
    return run_inference(image, prompt)

# --- 4. Main Execution Loop ---

if __name__ == "__main__":
    exp = topo.TopologicalExperiment()
    
    # Let's test one specific hard case: Partial Overlap (PO)
    print("\n--- Generating Stimuli: Partial Overlap ---")
    shape_a, shape_b = exp.generate_sample("PO")
    ground_truth = "PO (Partial Overlap)"
    
    # 1. Test Condition A
    result_a = run_condition_a_vision(exp, shape_a, shape_b)
    print(f"Condition A Result: {result_a}")
    
    # 2. Test Condition B
    result_b = run_condition_b_coordinates(shape_a, shape_b)
    print(f"Condition B Result: {result_b}")
    
    # 3. Test Condition C
    result_c = run_condition_c_visual_cues(exp, shape_a, shape_b)
    print(f"Condition C Result: {result_c}")
    
    print(f"\nGround Truth was: {ground_truth}")