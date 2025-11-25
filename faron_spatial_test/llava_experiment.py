import torch
from transformers import AutoProcessor, Qwen3VLMoeForConditionalGeneration, AutoModelForImageTextToText
from PIL import Image
import topology_generator as topo # Imports the file created above

# print("Loading LLaVA Model...")
model_id = "Qwen/Qwen3-VL-8B-Thinking" 

processor = AutoProcessor.from_pretrained(model_id) 
model = AutoModelForImageTextToText.from_pretrained(
    model_id,
    dtype=torch.float16,
    low_cpu_mem_usage=True,
    device_map='auto'
)

def run_inference(image, 
                  text_prompt:str):
    
    if image:
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "url": image},
                    {"type": "text", "text": text_prompt},
                ],
            },
        ]
    else:
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text_prompt},
                ],
            },
        ]

    inputs = processor.apply_chat_template(conversation, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt")
    inputs = inputs.to(model.device, torch.float16)
        
    output = model.generate(**inputs, max_new_tokens=512)
    response = processor.decode(output[0][inputs["input_ids"].shape[-1]:])
    
    print(response)

    try:
        return response.split("assistant")[1].strip()
    except:
        return response


def run_condition_a_vision(experiment, shape_a, shape_b, shape_c):
    """
    Get vision only
    """

    print("Condition A (Vision Only)")
    figure_name = experiment.render_to_pil(shape_a, shape_b, shape_c, visual_cues=False)
    
    prompt = (
        "Analyze the spatial relationship between the Red Object and the Blue Object. "
        "Choose exactly one of the following: Disconnected, Touching, Overlapping, Equal, "
        "Red is Inside Blue, or Blue is Inside Red."
    )
    
    return run_inference(figure_name, prompt)

def run_condition_b_coordinates(shape_a, shape_b, shape_c):
    """
    By text
    """
    print("Condition B (Text Only)")
    
    dummy_image = None
    
    bounds_a = [(round(x, 1), round(y, 1)) for x, y in shape_a.exterior.coords[:-1]]
    bounds_b = [(round(x, 1), round(y, 1)) for x, y in shape_b.exterior.coords[:-1]]

    # print(bounds_a)
    # print(bounds_b)
    
    prompt = (
        f"I am providing bounding box coordinates for two objects.\n"
        f"Object A (Red): {bounds_a}\n"
        f"Object B (Blue): {bounds_b}\n"
        "Based on these numbers, what is the topological relationship? "
        "Are they Disconnected, Touching, Overlapping, Equal, or one Inside the other?"
    )
    
    return run_inference(dummy_image, prompt)


def run_condition_c_visual_cues(experiment, shape_a, shape_b, shape_c):
    """
    With bbox
    """
    print("Condition C (With bbox)")
    
    figure_name = experiment.render_to_pil(shape_a, shape_b, shape_c, visual_cues=True)
    
    prompt = (
        "I have drawn dashed bounding boxes around the Red Object and the Blue Object to help you. "
        "Look at the boundaries indicated by the dashed lines. "
        "What is the topological relationship? (Disconnected, Touching, Overlapping, Inside, Equal)"
    )
    
    return run_inference(figure_name, prompt)


if __name__ == "__main__":
    confound = False

    for i in range(1):
        exp = topo.TopologicalExperiment()

        dict_rela = {
            "DC": "Disconnected",
            "EC": "Externally Connected",
            "PO": "Partially Overlapping",
            "EQ": "Equal",
            "TPP": "Tangential Proper Part",    # touching within
            "nTPP": "non-Tangential Proper Part",   # not touching within
        }

        test_rela = "nTPP"
        
        shape_a, shape_b = exp.generate_sample(test_rela)
        ground_truth = test_rela

        if confound:
            shape_c = exp.generate_confounder(shape_a, shape_b)
        else: shape_c = None
        
        result_a = run_condition_a_vision(exp, shape_a, shape_b, shape_c)
        print(f"Condition A Result: {result_a}\n")
        
        # result_b = run_condition_b_coordinates(shape_a, shape_b, shape_c)
        # print(f"Condition B Result: {result_b}\n")
        
        # result_c = run_condition_c_visual_cues(exp, shape_a, shape_b, shape_c)
        # print(f"Condition C Result: {result_c}\n")
        
        # print(f"\nGround Truth: {dict_rela[ground_truth]}")