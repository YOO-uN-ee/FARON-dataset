import random

def generate_geometry_question_and_sql(table_name="polygons", geom_column="geom"):
    """
    Generates a multi-step reasoning question and the corresponding PostGIS/SQL
    query based on topological relationships.

    The function assumes a PostgreSQL table named 'polygons' with a PostGIS
    geometry column named 'geom'.

    Args:
        table_name (str): The name of the polygon table.
        geom_column (str): The name of the geometry column.

    Returns:
        dict: A dictionary containing the question, reasoning steps, and SQL query.
    """

    # TODO: TEMPORARY PLACE HOLDERS    
    polygon_entities = ["Polygon_A", "Polygon_B", "Point_C", "Line_D"]
    
    # Select two main entities for the question
    entity1, entity2 = random.sample(polygon_entities, 2)
    
    # Select a third entity to introduce the 'multi-step' reasoning
    entity3 = random.choice([e for e in polygon_entities if e not in [entity1, entity2]])

    relationships = {
        "intersects": "ST_Intersects({col1}, {col2})",
        "contains": "ST_Contains({col1}, {col2})",
        "within": "ST_Within({col1}, {col2})",
        "overlaps": "ST_Overlaps({col1}, {col2})",
        "touches": "ST_Touches({col1}, {col2})",
        "disjoint": "ST_Disjoint({col1}, {col2})",
        "crosses": "ST_Crosses({col1}, {col2})"
    }
    
    # Choose two distinct relationships for the two steps
    rel_step1_name, rel_step1_sql_template = random.choice(list(relationships.items()))
    rel_step2_name, rel_step2_sql_template = random.choice(list(relationships.items()))

    # Find relation to entity1
    step1_query = f"""
    SELECT t2.name
    FROM {table_name} AS t1, {table_name} AS t2
    WHERE t1.name = '{entity1}'
      AND {rel_step1_sql_template.format(col1='t1.' + geom_column, col2='t2.' + geom_column)}
      AND t2.name != '{entity1}'
    """
        
    # Question
    question = (
        f"Question: "
        f"Which objects in the database {rel_step2_name} the '{entity2}', "
        f"but also {rel_step1_name} the '{entity1}'? "
        f"List only the names of the resulting polygons."
    )
    
    # Generate the combined SQL query using a Subquery/CTE for multi-step logic

    sql_query = f"""EXPLAIN ANALYZE
    WITH Related_to_{entity1} AS (
        SELECT t2.name, t2.{geom_column}
        FROM {table_name} AS t1, {table_name} AS t2
        WHERE t1.name = '{entity1}'
          AND {rel_step1_sql_template.format(col1='t1.' + geom_column, col2='t2.' + geom_column)}
          AND t2.name != '{entity1}'
    )
    
    SELECT T1.name
    FROM Related_to_{entity1} AS T1, {table_name} AS T2
    WHERE T2.name = '{entity2}'
      AND {rel_step2_sql_template.format(col1='T1.' + geom_column, col2='T2.' + geom_column)};
    """
    
    reasoning_steps = [
        f"Step 1 (Filtering by {entity1}): Identify the set of all shape(s) that have a '{rel_step1_name}' topological relationship with the '{entity1}'",
        f"Step 2 (Filtering by {entity2}): From the results of Step 1 further filter this set to include only the polygons that also have a '{rel_step2_name}' topological relationship with the '{entity2}'.",
        "Step 3 (Output): Return the names of the shape(s) remaining after both filtering steps."
    ]

    return {
        "Question": question.strip(),
        "Reasoning Steps": reasoning_steps,
        "PostgreSQL/PostGIS Query": sql_query.strip()
    }

# --- Example Usage ---
result = generate_geometry_question_and_sql(table_name="parcels", geom_column="shape_geom")

### The Multi-Step Question
print(result["Question"] + "\n")

### The Reasoning Steps
for step in result["Reasoning Steps"]:
    print(f"* {step}")
print("\n")

### The PostGIS/PostgreSQL Code
# TODO: Need to save to text file (.sql)
print(result["PostgreSQL/PostGIS Query"])   # TODO: Test if the code actually runs