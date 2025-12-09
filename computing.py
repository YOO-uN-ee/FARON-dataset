# import random
# import psycopg2
# import json
# from collections import defaultdict

# def generate_spatial_question_with_directions(
#     data, 
#     table_name="geometries",
#     name_col="name", 
#     geom_col="geom",
#     geom_type_col="geom_type",
#     tolerance=1.0
# ):
#     # 1. Define Standard Topological SQL Functions
#     sql_functions = {
#         "within": "ST_Covers({B}, {A})", 
#         "contain": "ST_Covers({A}, {B})",
#         "overlap": "ST_Overlaps({A}, {B})",
#         "intersect": "ST_Intersects({A}, {B})",
#         "disjoint": "ST_Disjoint({A}, {B})",
#         "crosses": "ST_Crosses({A}, {B})",
#         "touches": "ST_Touches({A}, {B})",
#         "borders": f"ST_DWithin({{A}}, {{B}}, {tolerance})"
#     }

#     # 2. Define Directional Ranges (Degrees) for SQL Generation
#     direction_map = {
#         "North":      (337.5, 22.5),
#         "North East": (22.5,  67.5),
#         "East":       (67.5,  112.5),
#         "South East": (112.5, 157.5),
#         "South":      (157.5, 202.5),
#         "South West": (202.5, 247.5),
#         "West":       (247.5, 292.5),
#         "North West": (292.5, 337.5)
#     }

#     SYMMETRIC_RELATIONS = ["borders", "intersect", "overlap", "disjoint", "crosses", "touches"]

#     # 3. Helper: Generate SQL for Azimuth/Direction
#     def get_sql_condition(rel, col_a, col_b):
#         """Returns the SQL WHERE clause for a given relationship."""
#         if rel in sql_functions:
#             return sql_functions[rel].format(A=col_a, B=col_b)
        
#         elif rel in direction_map:
#             # Direction: Target (A) is [Direction] of Source (B)
#             # ST_Azimuth(Source, Target) -> Angle from B to A
#             low, high = direction_map[rel]
#             azimuth_calc = f"degrees(ST_Azimuth(ST_Centroid({col_b}), ST_Centroid({col_a})))"
            
#             if rel == "North":
#                 # Special case for North wrapping around 0/360
#                 return f"({azimuth_calc} >= {low} OR {azimuth_calc} < {high})"
#             else:
#                 return f"({azimuth_calc} >= {low} AND {azimuth_calc} < {high})"
#         return "FALSE" # Fallback

#     # 4. Build Relationship Lookup (Graph)
#     # relations_map[Target] = [ (Source, Relation), ... ]
#     relations_map = defaultdict(list)
    
#     for a_info, b_info, rel in data:
#         a_key = tuple(a_info) # (Type, ID)
#         b_key = tuple(b_info)
        
#         # A is [rel] B
#         relations_map[a_key].append((b_key, rel))

#         # Handle Symmetry (If A touches B, B touches A)
#         if rel in SYMMETRIC_RELATIONS:
#             relations_map[b_key].append((a_key, rel))

#     # 5. Helper: Check Uniqueness (Ambiguity Filter)
#     def check_uniqueness(target_key, conditions):
#         """
#         Scans the entire dataset to ensure 'target_key' is the ONLY entity
#         that satisfies ALL 'conditions'.
#         conditions = [ (Source_Key, Relation), ... ]
#         """
#         valid_candidates = 0
        
#         # Iterate over every possible entity in the map to see if it matches
#         for candidate, candidate_rels in relations_map.items():
            
#             # Check if this candidate satisfies ALL conditions
#             matches_all = True
#             for req_source, req_rel in conditions:
#                 # Does candidate have (req_source, req_rel) in its history?
#                 if (req_source, req_rel) not in candidate_rels:
#                     matches_all = False
#                     break
            
#             if matches_all:
#                 valid_candidates += 1
        
#         # We want exactly 1 match (the target itself)
#         return valid_candidates == 1

#     # --- Template: Chained Relationship with Direction ---
#     # "Find the [Target] that is [Rel1] [Bridge] and [Bridge] is [Rel2] [Seed]"
#     def template_chained(template_data):
#         # Pick a random target that has at least one relationship
#         all_targets = list(relations_map.keys())
#         if not all_targets: return None
#         random.shuffle(all_targets)

#         for target_key in all_targets:
#             # Look at Target's relationships to find a "Bridge"
#             if not relations_map[target_key]: continue
            
#             bridge_key, rel_1 = random.choice(relations_map[target_key])
            
#             # Look at Bridge's relationships to find a "Seed" (that isn't the Target)
#             if not relations_map[bridge_key]: continue
            
#             # Filter bridge relations to avoid looping back to target
#             valid_seeds = [x for x in relations_map[bridge_key] if x[0] != target_key]
#             if not valid_seeds: continue
            
#             seed_key, rel_2 = random.choice(valid_seeds)

#             # --- AMBIGUITY CHECK ---
#             # We are asking: Find X where (X rel1 Bridge) AND (Bridge rel2 Seed)
#             # The ambiguity check for the "Bridge" is crucial if we reference it by description.
#             # But simpler logic: "Find X that is [Rel1] [Bridge_ID]." -> Check if X is unique for that bridge.
            
#             # Let's try a strict check: "Find the [Type] that is [Rel1] [Bridge_ID]"
#             # We only proceed if this specific combination is unique.
#             if not check_uniqueness(target_key, [(bridge_key, rel_1)]):
#                 # If "North of P0" yields 2 results, we can't use this simple form.
#                 # We could try to add the second hop to clarify, but for now, let's skip.
#                 continue

#             # Unpack
#             type_a, id_a = target_key
#             type_b, id_b = bridge_key
#             type_c, id_c = seed_key

#             # Construct SQL
#             cond_1_sql = get_sql_condition(rel_1, 'T_Final.'+geom_col, 'T_Bridge.'+geom_col)
#             cond_2_sql = get_sql_condition(rel_2, 'T_Bridge.'+geom_col, 'T_Seed.'+geom_col)

#             question = f"What is the {type_a} that is {rel_1} the {type_b} that is {rel_2} {id_c}?"

#             reasoning = [
#                 f"Step 1: Locate {id_c}.",
#                 f"Step 2: Find the {type_b} that matches '{rel_2}' with {id_c}.",
#                 f"Step 3: Find the {type_a} that matches '{rel_1}' with {id_b}."
#             ]

#             sql = f"""
# SELECT T_Final.{name_col}
# FROM {table_name} AS T_Final
# JOIN {table_name} AS T_Bridge ON {cond_1_sql}
# JOIN {table_name} AS T_Seed ON {cond_2_sql}
# WHERE
#     T_Final.{geom_type_col} = '{type_a}'
#     AND T_Bridge.{name_col} = '{id_b}'
#     AND T_Seed.{name_col} = '{id_c}'
#     AND T_Final.{name_col} <> T_Bridge.{name_col};
#             """
#             return {"question": question, "reasoning": reasoning, "sql": sql}
#         return None

#     def template_intersection(template_data):
#         candidates = [k for k, v in relations_map.items() if len(v) >= 2]
#         if not candidates: return None
#         random.shuffle(candidates)

#         for target_key in candidates:
#             cond1, cond2 = random.sample(relations_map[target_key], 2)
            
#             source1_key, rel1 = cond1
#             source2_key, rel2 = cond2

#             if not check_uniqueness(target_key, [cond1, cond2]):
#                 continue

#             # Unpack
#             type_t, id_t = target_key
#             type_s1, id_s1 = source1_key
#             type_s2, id_s2 = source2_key

#             # Build Question
#             question = f"Identify the {type_t} that is both {rel1} {id_s1} and {rel2} {id_s2}."

#             reasoning = [
#                 f"Step 1: Find {type_t}s that are {rel1} {id_s1}.",
#                 f"Step 2: Filter that list for items that are also {rel2} {id_s2}.",
#             ]

#             # Build SQL
#             sql_cond1 = get_sql_condition(rel1, 'T_Target.'+geom_col, 'T_S1.'+geom_col)
#             sql_cond2 = get_sql_condition(rel2, 'T_Target.'+geom_col, 'T_S2.'+geom_col)

#             sql = f"""
# SELECT T_Target.{name_col}
# FROM {table_name} AS T_Target
# JOIN {table_name} AS T_S1 ON {sql_cond1}
# JOIN {table_name} AS T_S2 ON {sql_cond2}
# WHERE
#     T_Target.{geom_type_col} = '{type_t}'
#     AND T_S1.{name_col} = '{id_s1}'
#     AND T_S2.{name_col} = '{id_s2}'
#     AND T_Target.{name_col} <> T_S1.{name_col}
#     AND T_Target.{name_col} <> T_S2.{name_col};
#             """
#             return {"question": question, "reasoning": reasoning, "sql": sql}
#         return None

#     # --- Execution Loop ---
#     possible_templates = [template_chained, template_intersection]
    
#     for _ in range(50): # Retry limit for finding unique questions
#         tmpl = random.choice(possible_templates)
#         res = tmpl({})
#         if res:
#             # Clean up SQL whitespace
#             res['sql'] = "\n".join([x.strip() for x in res['sql'].split('\n') if x.strip()])
#             return res

#     return {"error": "Could not generate a unique, non-ambiguous question from this data."}

import random
import psycopg2
import json
from collections import defaultdict

def generate_spatial_question_with_directions(
    data, 
    table_name="geometries",
    name_col="name", 
    geom_col="geom",
    geom_type_col="geom_type",
    tolerance=1.0
):
    # 1. Define Standard Topological SQL Functions
    sql_functions = {
        "within": "ST_Covers({B}, {A})", 
        "contain": "ST_Covers({A}, {B})",
        "overlap": "ST_Overlaps({A}, {B})",
        "intersect": "ST_Intersects({A}, {B})",
        "disjoint": "ST_Disjoint({A}, {B})",
        "crosses": "ST_Crosses({A}, {B})",
        "touches": "ST_Touches({A}, {B})",
        "borders": f"ST_DWithin({{A}}, {{B}}, {tolerance})"
    }

    # 2. Define Directional Ranges (Degrees) for SQL Generation
    direction_map = {
        "North":      (337.5, 22.5),
        "North East": (22.5,  67.5),
        "East":       (67.5,  112.5),
        "South East": (112.5, 157.5),
        "South":      (157.5, 202.5),
        "South West": (202.5, 247.5),
        "West":       (247.5, 292.5),
        "North West": (292.5, 337.5)
    }

    SYMMETRIC_RELATIONS = ["borders", "intersect", "overlap", "disjoint", "crosses", "touches"]

    # 3. Helper: Generate SQL for Azimuth/Direction
    def get_sql_condition(rel, col_a, col_b):
        """Returns the SQL WHERE clause for a given relationship."""
        if rel in sql_functions:
            return sql_functions[rel].format(A=col_a, B=col_b)
        
        elif rel in direction_map:
            low, high = direction_map[rel]
            azimuth_calc = f"degrees(ST_Azimuth(ST_Centroid({col_b}), ST_Centroid({col_a})))"
            
            if rel == "North":
                return f"({azimuth_calc} >= {low} OR {azimuth_calc} < {high})"
            else:
                return f"({azimuth_calc} >= {low} AND {azimuth_calc} < {high})"
        return "FALSE" 

    # 4. Build Relationship Lookup (Graph)
    # CHANGED: Use 'set' instead of 'list' to automatically deduplicate relations
    relations_map = defaultdict(set)
    
    for a_info, b_info, rel in data:
        a_key = tuple(a_info) # (Type, ID)
        b_key = tuple(b_info)
        
        # A is [rel] B
        relations_map[a_key].add((b_key, rel))

        # Handle Symmetry
        if rel in SYMMETRIC_RELATIONS:
            relations_map[b_key].add((a_key, rel))

    # 5. Helper: Check Uniqueness (Ambiguity Filter)
    def check_uniqueness(target_key, conditions):
        valid_candidates = 0
        for candidate, candidate_rels in relations_map.items():
            matches_all = True
            for req_source, req_rel in conditions:
                if (req_source, req_rel) not in candidate_rels:
                    matches_all = False
                    break
            
            if matches_all:
                valid_candidates += 1
        return valid_candidates == 1

    # --- Template: Chained Relationship ---
    def template_chained(template_data):
        # Convert keys to list for shuffling
        all_targets = list(relations_map.keys())
        if not all_targets: return None
        random.shuffle(all_targets)

        for target_key in all_targets:
            # Convert set to list for random.choice
            target_rels = list(relations_map[target_key])
            if not target_rels: continue
            
            bridge_key, rel_1 = random.choice(target_rels)
            
            bridge_rels = list(relations_map[bridge_key])
            if not bridge_rels: continue
            
            # Filter bridge relations to avoid looping back to target
            valid_seeds = [x for x in bridge_rels if x[0] != target_key]
            if not valid_seeds: continue
            
            seed_key, rel_2 = random.choice(valid_seeds)

            if not check_uniqueness(target_key, [(bridge_key, rel_1)]):
                continue

            type_a, id_a = target_key
            type_b, id_b = bridge_key
            type_c, id_c = seed_key

            cond_1_sql = get_sql_condition(rel_1, 'T_Final.'+geom_col, 'T_Bridge.'+geom_col)
            cond_2_sql = get_sql_condition(rel_2, 'T_Bridge.'+geom_col, 'T_Seed.'+geom_col)

            question = f"What is the {type_a} that is {rel_1} the {type_b} that is {rel_2} {id_c}?"

            reasoning = [
                f"Step 1: Locate {id_c}.",
                f"Step 2: Find the {type_b} that matches '{rel_2}' with {id_c}.",
                f"Step 3: Find the {type_a} that matches '{rel_1}' with {id_b}."
            ]

            sql = f"""
SELECT T_Final.{name_col}
FROM {table_name} AS T_Final
JOIN {table_name} AS T_Bridge ON {cond_1_sql}
JOIN {table_name} AS T_Seed ON {cond_2_sql}
WHERE
    T_Final.{geom_type_col} = '{type_a}'
    AND T_Bridge.{name_col} = '{id_b}'
    AND T_Seed.{name_col} = '{id_c}'
    AND T_Final.{name_col} <> T_Bridge.{name_col};
            """
            return {"question": question, "reasoning": reasoning, "sql": sql}
        return None

    # --- Template: Intersection ---
    def template_intersection(template_data):
        # Candidates must have at least 2 unique relations
        candidates = [k for k, v in relations_map.items() if len(v) >= 2]
        if not candidates: return None
        random.shuffle(candidates)

        for target_key in candidates:
            # Convert set to list for sampling
            unique_rels = list(relations_map[target_key])
            
            # Pick 2 distinct conditions
            cond1, cond2 = random.sample(unique_rels, 2)
            
            source1_key, rel1 = cond1
            source2_key, rel2 = cond2
            
            # CHANGED: Prevent redundant circular checks (e.g., Borders P2 AND Overlaps P2)
            # We enforce that the two conditions must refer to DIFFERENT objects.
            id_s1 = source1_key[1]
            id_s2 = source2_key[1]
            if id_s1 == id_s2:
                continue

            # Ambiguity Check
            if not check_uniqueness(target_key, [cond1, cond2]):
                continue

            type_t, id_t = target_key

            question = f"Identify the {type_t} that is both {rel1} {id_s1} and {rel2} {id_s2}."

            reasoning = [
                f"Step 1: Find {type_t}s that are {rel1} {id_s1}.",
                f"Step 2: Filter that list for items that are also {rel2} {id_s2}.",
            ]

            sql_cond1 = get_sql_condition(rel1, 'T_Target.'+geom_col, 'T_S1.'+geom_col)
            sql_cond2 = get_sql_condition(rel2, 'T_Target.'+geom_col, 'T_S2.'+geom_col)

            sql = f"""
SELECT T_Target.{name_col}
FROM {table_name} AS T_Target
JOIN {table_name} AS T_S1 ON {sql_cond1}
JOIN {table_name} AS T_S2 ON {sql_cond2}
WHERE
    T_Target.{geom_type_col} = '{type_t}'
    AND T_S1.{name_col} = '{id_s1}'
    AND T_S2.{name_col} = '{id_s2}'
    AND T_Target.{name_col} <> T_S1.{name_col}
    AND T_Target.{name_col} <> T_S2.{name_col};
            """
            return {"question": question, "reasoning": reasoning, "sql": sql}
        return None

    # --- Execution Loop ---
    possible_templates = [template_chained, template_intersection]
    
    for _ in range(50): 
        tmpl = random.choice(possible_templates)
        res = tmpl({})
        if res:
            res['sql'] = "\n".join([x.strip() for x in res['sql'].split('\n') if x.strip()])
            return res

    return {"error": "Could not generate a unique, non-ambiguous question from this data."}

# --- Example Usage ---

# Load your relationship data
with open('./relationship.json', 'r') as file:
    sample_data = json.load(file)

# Generate the question
generated_data = generate_spatial_question_with_directions(
    sample_data["relationships"],
    table_name="generated_geometries",
    name_col="id",    
    geom_col="geom",
    geom_type_col="geom_type" 
)

with open('./question_detail.json', 'w') as f:
    json.dump(generated_data, f, indent=4)

if "error" in generated_data:
    print(generated_data["error"])
else:
    print("Question\n")
    print(generated_data['question'])
    print("\n" + "---" + "\n")

    print("Composition\n")
    for step in generated_data['reasoning']:
        print(f"* {step}")
    print("\n" + "---" + "\n")

    DB_CONFIG = {
        "dbname": "postgres",
        "user": "postgres",
        "password": "jiYOON7162@",
        "host": "localhost",
        "port": "5432"
    }

    QUERY_TO_ANALYZE = generated_data['sql']
    OUTPUT_FILENAME = "query_plan.json"

    sql_explain_query = f"EXPLAIN (ANALYZE, FORMAT JSON) {QUERY_TO_ANALYZE}"

    plan_json = None

    try:
        print(f"Connecting to database '{DB_CONFIG['dbname']}'...")
        with psycopg2.connect(**DB_CONFIG) as conn:
            print("Connection successful.")
            
            with conn.cursor() as cur:
                
                print(f"Executing: {sql_explain_query}")
                cur.execute(sql_explain_query)
                
                plan_result = cur.fetchone()
                
                if plan_result:
                    plan_json = plan_result[0]
                else:
                    print("Error: Could not retrieve an explain plan.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Database error: {error}")

    # --- Save to File ---
    if plan_json:
        try:
            print(f"Saving query plan to '{OUTPUT_FILENAME}'...")
            with open(OUTPUT_FILENAME, 'w') as f:
                json.dump(plan_json, f, indent=4)
            
            print(f"Successfully saved query plan to '{OUTPUT_FILENAME}'.")
        except (Exception, IOError) as error:
            print(f"Error writing to file: {error}")