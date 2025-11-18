# plan_parser.py

import json
import random
import string
from plan_node import PlanNode  # Assumes plan_node.py is in the same directory

def _create_random_name():
    """Generates a random temp_xxxxxxxx table name."""
    chars = string.ascii_lowercase
    return "temp_" + "".join(random.choices(chars, k=8))

def parse_explain_json(plan_json_string: str) -> PlanNode:
    """
    Parses the full JSON output from an EXPLAIN command.
    """
    try:
        data = json.loads(plan_json_string)
        if not data or not isinstance(data, list) or 'Plan' not in data[0]:
            raise ValueError("Invalid EXPLAIN JSON format. Expected a list with a 'Plan' key.")
            
        root_plan_dict = data[0]['Plan']
        root_node = PlanNode(root_plan_dict, level=0)
        return root_node
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        raise

def generate_sql_steps(root_node: PlanNode) -> list[dict]:
    """
    Performs a post-order traversal (DFS) to generate a
    list of SQL steps, each creating a temp table.
    
    Returns:
        A list of dictionaries, each representing an executable step.
    """
    sql_steps = []
    
    def _dfs_post_order(current_node: PlanNode):
        # 1. Visit children first (so their temp tables are created)
        for child in current_node.children:
            _dfs_post_order(child)
            
        # 2. Process this node (after children are processed)
        
        # Generate the 'SELECT ...' part of the query
        select_sql = current_node._generate_select_sql()
        
        if select_sql is None:
            # This is a "meta" node (like Hash, Bitmap Index Scan)
            # It doesn't get its own SQL step. Its logic is
            # "absorbed" by its parent. We just return.
            return

        # This is a node that produces a row set.
        # Give it a new temp table name.
        current_node.temp_table_name = _create_random_name()
        
        # Create the full DDL command
        full_sql = f"CREATE TEMPORARY TABLE {current_node.temp_table_name} AS ({select_sql});"
        
        # Store the full SQL command on the node itself
        current_node.operation_sql = full_sql
        
        # Add this step to our final list
        sql_steps.append({
            "node_type": current_node.node_type,
            "level": current_node.level,
            "temp_table": current_node.temp_table_name,
            "sql_command": full_sql
        })

    # Start the traversal
    if root_node:
        _dfs_post_order(root_node)
        
    return sql_steps