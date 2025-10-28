import random
import json
from collections import defaultdict

def get_type(entity_name):
    """Extracts the type (POLYGON, LINE, POINT) from a name.
    TODO: Change it to Shapely so that SQL not rely on name but on shape form?
    TODO: Or add category that is polygon, line, point when generating"""
    return entity_name.split('_')[0]

def generate_spatial_question_from_data_with_postgis(
    data, 
    table_name="geometries", 
    name_col="name", 
    geom_col="geom"
):
    """
    Generates a data-driven multi-step question and its PostGIS SQL.
    
    Args:
        data (list): A list of relationships
        table_name (str): Name of the geometry table.
        name_col (str): Name of the name/ID column.
        geom_col (str): Name of the geometry column.
    """
    
    sql_functions = {
        "within": "ST_Within({A}, {B})",
        "contain": "ST_Contains({A}, {B})",
        "overlap": "ST_Overlaps({A}, {B})",
        "intersect": "ST_Intersects({A}, {B})",
        "disjoint": "ST_Disjoint({A}, {B})",
        "crosses": "ST_Crosses({A}, {B})"
    }
    
    relations_of_a = defaultdict(list)
    relations_of_b = defaultdict(list)
    
    for a, b, rel in data:
        if rel in sql_functions:
            relations_of_a[a].append((b, rel))
            relations_of_b[b].append((a, rel))

    def template_chained_relationship(template_data):
        """
        Find chain: A -> [Rel1] -> B -> [Rel2] -> C
        Generates question: Find A that [Rel1] B, where B [Rel2] C.
        """
        # Find a valid chain (A -> B -> C)
        # B object in at leat one relation and a subject in one other
        possible_b = list(set(relations_of_a.keys()) & set(relations_of_b.keys()))
        if not possible_b:
            return None # No chains found

        entity_b = random.choice(possible_b)
        
        # Find A -> Rel1 -> B
        entity_a, rel_1_name = random.choice(relations_of_b[entity_b])
        
        # Find B -> Rel2 -> C
        entity_c, rel_2_name = random.choice(relations_of_a[entity_b])
        
        # Get types
        type_a = get_type(entity_a)
        type_b = get_type(entity_b)

        # Get SQL functions
        rel_1_sql = template_data['sql_functions'][rel_1_name]
        rel_2_sql = template_data['sql_functions'][rel_2_name]

        # Build Question
        question = (
            f"Which {type_a}s in the database {rel_1_name} the {type_b} "
            f"that is {rel_2_name} {entity_c}?"
        )

        # Build Reasoning
        reasoning = [
            f"Step 1 (Intermediate Set): Find all `{type_b}` geometries that "
            f"`{rel_2_name}` (`{rel_2_sql.format(A='..', B='..')}`) '{entity_c}'.",
            
            f"Step 2 (Final Set): Find all `{type_a}` geometries that "
            f"`{rel_1_name}` (`{rel_1_sql.format(A='..', B='..')}`) "
            f"intermediate set.",
            
            "Step 3: Return the distinct names of these final geometries."
        ]
        
        # Build SQL
        sql = f"""
WITH IntermediateSet AS (
    SELECT T1.{template_data['geom_col']}
    FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
    WHERE
        T1.{template_data['name_col']} LIKE '{type_b}_%'
        AND T2.{template_data['name_col']} = '{entity_c}'
        AND {rel_2_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])}
)
SELECT DISTINCT T_Final.{template_data['name_col']}
FROM {template_data['table_name']} AS T_Final, IntermediateSet
WHERE
    T_Final.{template_data['name_col']} LIKE '{type_a}_%'
    AND {rel_1_sql.format(A='T_Final.' + template_data['geom_col'], B='IntermediateSet.' + template_data['geom_col'])};
        """
        return {"question": question, "reasoning": reasoning, "sql": sql}

    def template_multiple_conditions(template_data):
        """
        Finds a real entity A that has two+ relations:
        A -> Rel1 -> B
        A -> Rel2 -> C
        Generates question: Find A that [Rel1] B AND [Rel2] C.
        """
        possible_a = [a for a, rels in template_data['relations_of_a'].items() if len(rels) >= 2]
        if not possible_a:
            return None
            
        entity_a = random.choice(possible_a)
        
        (entity_b, rel_1_name), (entity_c, rel_2_name) = random.sample(
            template_data['relations_of_a'][entity_a], 2
        )
        
        # Get types and SQL
        type_a = get_type(entity_a)
        rel_1_sql = template_data['sql_functions'][rel_1_name]
        rel_2_sql = template_data['sql_functions'][rel_2_name]

        # Build Question
        question = (
            f"Find all {type_a}s that both "
            f"{rel_1_name} '{entity_b}' AND "
            f"{rel_2_name} '{entity_c}'."
        )

        # Build Reasoning
        reasoning = [
            f"Step 1: Find the set of all `{type_a}`s that `{rel_1_name}` "
            f"(using `{rel_1_sql.format(A='..', B='..')}`) '{entity_b}'.",
            f"Step 2: Find the set of all `{type_a}`s that `{rel_2_name}` "
            f"(using `{rel_2_sql.format(A='..', B='..')}`) '{entity_c}'.",
            "Step 3: Find the common geometries (the intersection) "
            "between the sets from Step 1 and Step 2."
        ]
        
        sql = f"""
SELECT T1.{template_data['name_col']}
FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
WHERE
    T1.{template_data['name_col']} LIKE '{type_a}_%'
    AND T2.{template_data['name_col']} = '{entity_b}'
    AND {rel_1_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])}

INTERSECT
SELECT T1.{template_data['name_col']}
FROM {template_data['table_name']} AS T1, {template_data['table_name']} AS T2
WHERE
    T1.{template_data['name_col']} LIKE '{type_a}_%'
    AND T2.{template_data['name_col']} = '{entity_c}'
    AND {rel_2_sql.format(A='T1.' + template_data['geom_col'], B='T2.' + template_data['geom_col'])};
        """
        return {"question": question, "reasoning": reasoning, "sql": sql}

    template_data = {
        "table_name": table_name,
        "name_col": name_col,
        "geom_col": geom_col,
        "sql_functions": sql_functions,
        "relations_of_a": relations_of_a,
        "relations_of_b": relations_of_b
    }

    # Find which templates are possible with the given data
    possible_templates = []
    
    # Check for multi-condition patterns
    if any(len(rels) >= 2 for rels in relations_of_a.values()):
        possible_templates.append(template_multiple_conditions)
        
    # Check for chained-relationship patterns
    if (set(relations_of_a.keys()) & set(relations_of_b.keys())):
        possible_templates.append(template_chained_relationship)


    if not possible_templates:
        return {"error": "Could not find any multi-step patterns in the provided data."}

    # Pick a random possible template and run it
    chosen_template = random.choice(possible_templates)
    result = chosen_template(template_data)
    
    # Clean up SQL formatting
    if result and 'sql' in result:
        result['sql'] = "\n".join(
            [line.strip() for line in result['sql'].strip().split('\n') if line.strip()]
        )
    
    return result









with open('./relationship.json', 'r') as file:
    sample_data = json.load(file)

generated_data = generate_spatial_question_from_data_with_postgis(
    sample_data["relationships"],
    table_name="generated_geometries", 
    name_col="name", 
    geom_col="geom"
)

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

    print("PostGIS/PostgreSQL Query\n")
    print("```sql")
    print("EXPLAIN (ANALYZE, BUFFERS)")
    print(generated_data['sql'])
    print("```")