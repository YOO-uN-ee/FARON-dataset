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

# --- INPUT DATA ---

with open('border1/question_detail.json', 'r') as file:
    question_data = json.load(file)

with open('border1/execution_io.txt', 'r') as f:
    sql_log_raw = f.read()

# Helper to clean log (keep Output lines, remove technical headers)
def clean_log(text):
    text = re.sub(r'-- Output Table: .*', '', text)
    text = re.sub(r'-- Input: .*', '', text)
    return text

cleaned_sql = clean_log(sql_log_raw)

# --- THE SYSTEM PROMPT ---
system_prompt = """
You are a Logic Synthesizer. You are given a "Reasoning Plan" (the intent) and a "SQL Execution Log" (the actual results).
Your goal is to rewrite the Reasoning Plan using the specific data found in the Log.

**ALGORITHM:**
1. **Initialize:** Start by stating the object found in the first SQL Step (usually the anchor, e.g., "Find P2").
2. **Map Steps:** Match each step in the "Reasoning Plan" to the corresponding "Active Step" in the SQL Log. 
   - (Note: Ignore SQL steps that just scan tables; look for the JOINs).
3. **Substitute Variables:** - Look at the `reasoning`: "Find points... matching results from Step 1".
   - Look at the `SQL Log` for that step: Find the line `-- Output: [VALUES]`.
   - **CRITICAL:** Replace "results from Step 1" with the specific values found (e.g., "P1").
4. **Format:** Output a concise numbered list. Use the verbs from the Reasoning (e.g., "borders", "within") but the nouns from the SQL Log.

**EXAMPLE:**
*Reasoning:* Find polygons bordering P2. Find points within those polygons.
*SQL Log:* Step 3 Output: P1. Step 5 Output: Pt5.
*Output:*
1. Find P2.
2. Find polygons that border P2.
3. Find points that are within P1.
"""

# Format input as a single prompt block
user_content = f"""
**Reasoning Plan:**
{json.dumps(question_data['reasoning'], indent=2)}

**SQL Execution Log:**
{cleaned_sql}
"""

print(user_content)

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_content},
]

outputs = pipe(
    messages,
    max_new_tokens=256,
    eos_token_id=pipe.tokenizer.eos_token_id,
    do_sample=True,
    temperature=0.1,
)

print(outputs[0]["generated_text"][-1]['content'])