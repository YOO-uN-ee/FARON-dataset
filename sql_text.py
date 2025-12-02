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
5. **NO TECHNICAL JARGON:** Do not use words like "Table", "Step", "ID", "Database", "Scan", or "Sort".

**EXAMPLES:**
Input: CREATE TEMP TABLE x AS SELECT * FROM data WHERE id = 'P1'
Output: Find the item with ID 'P1'.

Input: SELECT * FROM t1 JOIN t2 ON st_within(t1.geom, t2.geom)
Output: Find which items from the previous step are within the area found in step 2.
"""

user1 = """
--- SQL Steps in Execution Order ---

-- Step 1 (L4: Index Scan) --
-- Output Table: temp_bmwrvhea
CREATE TEMPORARY TABLE temp_bmwrvhea AS (SELECT * FROM public.generated_geometries WHERE ((id)::text = 'P2'::text) AND (((geom_type)::text = 'Polygon'::text)));

-- Step 2 (L4: Seq Scan) --
-- Output Table: temp_tgdrnrgi
CREATE TEMPORARY TABLE temp_tgdrnrgi AS (SELECT * FROM public.generated_geometries WHERE ((geom_type)::text = 'Polygon'::text));

-- Step 3 (L3: Nested Loop) --
-- Output Table: temp_rytixqwn
CREATE TEMPORARY TABLE temp_rytixqwn AS (SELECT * FROM temp_bmwrvhea AS t2 INNER JOIN temp_tgdrnrgi AS t1 ON (((t1.id)::text <> (t2.id)::text) AND st_within(t1.geom, t2.geom)));

-- Step 4 (L3: Seq Scan) --
-- Output Table: temp_yvvfmuln
CREATE TEMPORARY TABLE temp_yvvfmuln AS (SELECT * FROM public.generated_geometries WHERE ((geom_type)::text = 'Point'::text));

-- Step 5 (L2: Nested Loop) --
-- Output Table: temp_pxxywyez
CREATE TEMPORARY TABLE temp_pxxywyez AS (SELECT * FROM temp_rytixqwn AS t2 INNER JOIN temp_yvvfmuln AS t_final ON st_within(t_final.geom, t2.geom));

-- Step 6 (L1: Sort) --
-- Output Table: temp_zgbvpjao
CREATE TEMPORARY TABLE temp_zgbvpjao AS (SELECT * FROM temp_pxxywyez AS t2 ORDER BY t2.id);

-- Step 7 (L0: Unique) --
-- Output Table: temp_dlwvgtgh
CREATE TEMPORARY TABLE temp_dlwvgtgh AS (SELECT * FROM (unknown_operation: Unique));

--- Final Query (Root Node) ---
The final result is in table: temp_dlwvgtgh
(Run 'SELECT * FROM temp_dlwvgtgh;' to see results)

"""

assistant1 = """
1. Find P2.
2. Check which polygons that are within P2.
3. Look at the points that lie inside that neighboring polygon (P1).
"""

# 3. Construct the Prompt
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": f"Translate these steps into a numbered list of natural language actions:\n\n{user1}"},
    {"role": "assistant", "content": assistant1},
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