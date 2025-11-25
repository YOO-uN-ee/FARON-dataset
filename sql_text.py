import json
import torch
from transformers import pipeline

# 1. Load the Model (Using Llama-3-8B-Instruct or Mistral)
model_id = "meta-llama/Meta-Llama-3-8B-Instruct" 

pipe = pipeline(
    "text-generation",
    model=model_id,
    model_kwargs={"torch_dtype": torch.bfloat16},
    device_map="auto",
)

# 2. Your Raw Input
with open('execution.txt', 'r') as f:
    sql_text = f.read()
# sql_text = """
# -- Step 1 (L4: Index Scan) --
# CREATE TEMPORARY TABLE temp_bmwrvhea AS (SELECT * FROM public.generated_geometries WHERE ((id)::text = 'P2'::text) AND (((geom_type)::text = 'Polygon'::text)));
# ... (rest of your SQL) ...
# """

# 3. Construct the Prompt
messages = [
    {"role": "system", "content": "You are a SQL to Natural Language translator. Summarize each step briefly. interpreting spatial functions like 'st_within' as 'inside'. Trace the temporary tables to explain the data flow."},
    {"role": "user", "content": f"Translate these steps into a numbered list of natural language actions:\n\n{sql_text}"},
]

# 4. Generate
outputs = pipe(
    messages,
    max_new_tokens=512,
    do_sample=True,
    temperature=0.1, # Keep low for factual accuracy
)

print(outputs[0]["generated_text"][-1]['content'])