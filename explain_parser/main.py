# main.py

import json
from plan_parser import parse_explain_json, generate_sql_steps

# --- YOUR PROVIDED JSON PLAN ---
OUTPUT_FILENAME = "query_plan.json"
query_plan_data = None

with open("../query_plan.json", 'r') as f:
    # Use json.load() to parse the file object into a Python object
    # query_plan_data = json.loads(f)
    PLAN_JSON = f.read()
    print(PLAN_JSON)

# PLAN_JSON = """
# [
#   {
#     "Plan": {
#       "Node Type": "Nested Loop",
#       "Parallel Aware": false,
#       "Join Type": "Left",
#       "Startup Cost": 11.95,
#       "Total Cost": 28.52,
#       "Plan Rows": 5,
#       "Plan Width": 157,
#       "Actual Startup Time": 0.007,
#       "Actual Total Time": 0.007,
#       "Actual Rows": 0,
#       "Actual Loops": 1,
#       "Inner Unique": true,
#       "Join Filter": "(exam_1.id = rel_users_exams.exam_id)",
#       "Plans": [
#         {
#           "Node Type": "Bitmap Heap Scan",
#           "Parent Relationship": "Outer",
#           "Relation Name": "rel_users_exams",
#           "Alias": "rel_users_exams",
#           "Startup Cost": 11.80,
#           "Total Cost": 20.27,
#           "Plan Rows": 5,
#           "Recheck Cond": "(1 = rel_users_exams.exam_id)",
#           "Plans": [
#             {
#               "Node Type": "Bitmap Index Scan",
#               "Parent Relationship": "Outer",
#               "Index Name": "rel_users_exams_pkey",
#               "Index Cond": "(1 = rel_users_exams.exam_id)"
#             }
#           ]
#         },
#         {
#           "Node Type": "Materialize",
#           "Parent Relationship": "Inner",
#           "Plans": [
#             {
#               "Node Type": "Index Scan",
#               "Parent Relationship": "Outer",
#               "Index Name": "exam_pkey",
#               "Relation Name": "exam",
#               "Alias": "exam_1",
#               "Index Cond": "(exam_1.id = 1)"
#             }
#           ]
#         }
#       ]
#     },
#     "Planning Time": 0.905,
#     "Triggers": [],
#     "Execution Time": 0.134
#   }
# ]
# """

if __name__ == "__main__":
    # 1. Parse the JSON into a tree of nodes
    root = parse_explain_json(PLAN_JSON)
    
    # 2. Generate the list of SQL steps in execution order
    execution_steps = generate_sql_steps(root)
    
    print("--- SQL Steps in Execution Order ---")
    
    if not execution_steps:
        print("No executable SQL steps were generated.")
    else:
        for i, step in enumerate(execution_steps):
            print(f"\n-- Step {i + 1} (L{step['level']}: {step['node_type']}) --")
            print(f"-- Output Table: {step['temp_table']}")
            print(step['sql_command'])
            
        print("\n--- Final Query (Root Node) ---")
        final_step = execution_steps[-1]
        print(f"The final result is in table: {final_step['temp_table']}")
        print(f"(Run 'SELECT * FROM {final_step['temp_table']};' to see results)")