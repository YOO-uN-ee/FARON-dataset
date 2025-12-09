import torch
from transformers import pipeline

def diversify_question(original_question):
    """
    Generates variations of a question using synonym replacement 
    and structural rewriting.
    """
    
    # 1. Initialize the pipeline
    # We continue using flan-t5-large as it is efficient for rewriting tasks.
    device = 0 if torch.cuda.is_available() else -1
    generator = pipeline(
        "text2text-generation", 
        model="google/flan-t5-large", 
        device=device
    )

    # 2. Construct the Prompt
    # This is the most critical part. We explicitly ask for specific types of changes.
    prompt = f"""
    Task: Paraphrase the following question in 3 distinct ways.
    
    Input Question: "{original_question}"
    
    Requirements:
    1. Grammar Fix: Strictly correct the grammar.
    2. Synonym Swap: Use different words (e.g., "contained by", "enclosed in", "adjacent", "neighboring").
    3. Structural Change: Rewrite the sentence structure entirely.
    
    Output:
    """

    # 3. Generate
    # do_sample=True allows the model to pick non-obvious words, increasing variety.
    outputs = generator(
        prompt, 
        max_length=200, 
        do_sample=True, 
        temperature=0.8
    )
    
    return outputs[0]['generated_text']

# --- Main Execution ---

if __name__ == "__main__":
    # Your raw input
    raw_question = "What is the Line that is within the Polygon that is borders P1?"
    
    print(f"--- Processing: '{raw_question}' ---\n")
    
    result = diversify_question(raw_question)
    
    # Simple parsing to display the results cleanly
    print("Generated Variations:")
    # The model usually separates lines with numbers like "1.", "2.", etc.
    print(result.replace(". 2", ".\n2").replace(". 3", ".\n3"))