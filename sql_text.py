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
Convert the SQL logs into a natural chain of events.

**PROCEDURE FOR EACH STEP:**
1.  **Decide to Speak or Skip:**
    * **SKIP** generic "Seq Scans" that just load all data (e.g. "Get all Polygons").
    * **SPEAK** if the step filters by a specific ID (e.g., 'P3') or performs a JOIN.

2.  **Determine the "Active Subject":**
    * Look at the temporary table being used. Find the `-- Output:` comment associated with that table in the previous steps.
    * *Example:* If Step 5 uses the table from Step 3, and Step 3 had `-- Output: P0`, then the subject is **P0**.

3.  **Construct the Sentence:**
    * **Start:** "Find the [Geometry Type] [ID]..."
    * **Chained Action:** "Find [Target Type] that are [Relation] [Active Subject]..."

4.  **Translate Relations:**
    * `st_covers(A, B)` -> B is inside A
    * `st_within(A, B)` -> A is inside B

**OUTPUT STYLE:**
Produce a numbered list. Be concise. Do not explain the code, just the data flow.
"""

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": f"Trace the data flow in this log:\n\n{cleaned_text}"},
]

outputs = pipe(
    messages,
    max_new_tokens=256,
    eos_token_id=pipe.tokenizer.eos_token_id,
    do_sample=True,
    temperature=0.1,
)

print(outputs[0]["generated_text"][-1]['content'])