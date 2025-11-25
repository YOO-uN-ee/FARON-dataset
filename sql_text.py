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

system_prompt = """
You are a GIS (Geographic Information System) assistant. 
Your goal is to describe database actions in simple, human commands.

**GUIDELINES:**
1. **FOCUS ON INTENT:** Look at the 'WHERE' clauses and 'JOIN' conditions to understand what is being filtered or connected.
2. **IGNORE BOILERPLATE:** Do NOT mention "creating temporary tables", "index scans", "sequences", or "selecting columns". 
3. **USE NATURAL VERBS:** Start sentences with "Find", "Select", "Filter", or "Identify".
4. **HANDLE SPATIAL LOGIC:** - `st_within(A, B)` -> "Find A that is within B"
   - `geom_type = 'Polygon'` -> "polygons"
   - `geom_type = 'Point'` -> "points"

**EXAMPLES:**
Input: CREATE TEMP TABLE x AS SELECT * FROM data WHERE id = 'P1'
Output: Find the item with ID 'P1'.

Input: SELECT * FROM t1 JOIN t2 ON st_within(t1.geom, t2.geom)
Output: Find which items from the previous step are within the area found in step 2.
"""

# 3. Construct the Prompt
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": f"Translate these steps into a numbered list of natural language actions:\n\n{sql_text}"},
]

# 4. Generate
outputs = pipe(
    messages,
    max_new_tokens=512,
    do_sample=True,
    temperature=0.01, # Keep low for factual accuracy
)

print(outputs[0]["generated_text"][-1]['content'])