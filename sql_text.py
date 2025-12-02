import json
import re
import torch
from transformers import pipeline

# 1. Load the Model (Using Llama-3-8B-Instruct or Mistral)
model_id = "meta-llama/Meta-Llama-3-8B-Instruct" 

pipe = pipeline(
    "text-generation",
    model=model_id,
    model_kwargs={"dtype": torch.bfloat16},
    device_map="auto",
)

# 2. Your Raw Input
with open('execution_io.txt', 'r') as f:
    sql_text = f.read()


def clean_log(text):
    # Remove lines about Input, Table names, or Scan types to reduce noise
    text = re.sub(r'-- Output Table: .*', '', text)
    text = re.sub(r'-- Input: .*', '', text) 
    # Keep "-- Output: ..." lines as they are crucial for your naming requirement
    return text

cleaned_text = clean_log(sql_text)

# 2. The Prompt
system_prompt = """
You are a SQL Execution Narrator. Convert the log into a numbered list of actions.

**RULES:**
1. **FILTERING (IGNORE):** - IGNORE steps that just "Get all Polygons" or "Get all Points" (Seq Scans without ID filters).
   - ONLY report steps that filter by a specific ID (e.g., 'P3') or perform a JOIN.

2. **NAMING (CRITICAL):**
   - Look at the `-- Output:` comment in the log.
   - When describing a step, use the **Output name** from the *previous* relevant step.
   - Example: If Step 3 Output is 'P0', then in Step 5 say "Find points within **P0**" instead of "Find points within the result of step 3".

3. **SPATIAL LOGIC:**
   - `st_covers(A, B)` -> "Find [B] that are within [A]"
   - `st_within(A, B)` -> "Find [A] that are within [B]"

**DESIRED FORMAT:**
1. Find the polygon with [ID]
2. Identify the polygons that are within [ID]
3. Find all points that are within [Result of Step 2]
"""

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": f"Translate this execution log based on the rules:\n\n{cleaned_text}"},
]

outputs = pipe(
    messages,
    max_new_tokens=256,
    eos_token_id=pipe.tokenizer.eos_token_id,
    do_sample=True,
    temperature=0.1,
)

print(outputs[0]["generated_text"][-1]['content'])