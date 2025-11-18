# plan_node.py
import random
import string

class PlanNode:
    """
    A class to represent a single node in a PostgreSQL execution plan.
    Properties are now set up to allow a post-order traversal
    to generate a series of executable, temporary-table-based SQL steps.
    """
    def __init__(self, plan_dict, level=0):
        self.level = level
        
        # --- Core Properties ---
        self.node_type = plan_dict.get('Node Type', 'N/A')
        self.relation_name = plan_dict.get('Relation Name')
        self.alias = plan_dict.get('Alias')
        
        # --- Cost and Time ---
        self.actual_total_time = plan_dict.get('Actual Total Time')
        self.actual_rows = plan_dict.get('Actual Rows')
        self.plan_rows = plan_dict.get('Plan Rows')
        
        # --- SQL-Relevant Properties ---
        self.filter = plan_dict.get('Filter')
        self.join_type = plan_dict.get('Join Type')
        self.join_condition = plan_dict.get('Join Cond')
        self.hash_condition = plan_dict.get('Hash Cond')
        self.merge_condition = plan_dict.get('Merge Cond')
        self.join_filter = plan_dict.get('Join Filter')
        self.index_name = plan_dict.get('Index Name')
        self.index_cond = plan_dict.get('Index Cond')
        self.recheck_cond = plan_dict.get('Recheck Cond')
        self.sort_key = plan_dict.get('Sort Key')
        
        # --- NEW Properties for SQL Generation ---
        # The alias this node's output will be known by (for joins)
        self.alias_name = self.alias or self.relation_name
        
        # These will be set by the parser during traversal
        self.temp_table_name = None 
        self.operation_sql = None

        # --- Recursive Parsing ---
        self.children = []
        if 'Plans' in plan_dict:
            for child_plan in plan_dict['Plans']:
                self.children.append(PlanNode(child_plan, level + 1))
        
        # --- NEW: Alias Inheritance ---
        # If this node is a wrapper (like Sort or Materialize)
        # and has no alias, it "inherits" the alias from its child
        # so a parent join knows what to call it.
        if not self.alias_name and self.children:
            self.alias_name = self.children[0].alias_name

    def _generate_select_sql(self) -> str | None:
        """
        Generates the 'SELECT ...' part of the SQL query for this node.
        This method ASSUMES all children have had their temp_table_name set.
        Returns None for "meta" nodes that don't produce a rowset themselves.
        """
        node_type = self.node_type
        
        # --- "Meta" nodes (absorbed by parents) ---
        if node_type in ("Bitmap Index Scan", "Hash"):
            # These steps are preparatory. Their logic is used
            # by their parent (Bitmap Heap Scan, Hash Join).
            # They don't produce a SQL-level temp table.
            return None

        # --- Scan Operations (Base cases) ---
        if node_type == "Seq Scan":
            sql = f"SELECT * FROM public.{self.relation_name}"
            if self.filter:
                sql += f" WHERE {self.filter}"
            return sql
        
        if node_type == "Index Scan":
            # Index Cond is the primary filter
            sql = f"SELECT * FROM public.{self.relation_name} WHERE {self.index_cond}"
            if self.filter:
                # Add any additional filter
                sql += f" AND ({self.filter})"
            return sql
        
        if node_type == "Bitmap Heap Scan":
            # This node *does* the scan, using its child's (Bitmap Index Scan) condition
            if not self.children or not self.children[0].index_cond:
                return f"SELECT * FROM public.{self.relation_name} -- (Error: Missing Bitmap Index Cond)"
                
            index_cond = self.children[0].index_cond
            sql = f"SELECT * FROM public.{self.relation_name} WHERE {index_cond}"
            if self.recheck_cond and self.recheck_cond != index_cond:
                 sql += f" -- (Recheck: {self.recheck_cond})"
            return sql

        # --- Wrapper Operations (on one child) ---
        if not self.children and node_type not in ("Seq Scan", "Index Scan"):
            # Handle nodes that might not have children but should
            return f"-- (Error: Node {node_type} has no children)"

        # Get the temp table of the *first* child (for Sort, Agg, etc.)
        child_table = self.children[0].temp_table_name

        if node_type == "Sort":
            return f"SELECT * FROM {child_table} ORDER BY {', '.join(self.sort_key)}"

        if node_type == "Materialize":
            # A "Materialize" node is just a cache.
            # We create a new temp table by selecting from its child's temp table.
            return f"SELECT * FROM {child_table}"
            
        if node_type in ("Agg", "HashAgg", "GroupAgg"):
             # This is a simplification; we're not parsing the 'Output' list
            sql = f"SELECT * FROM {child_table}"
            if self.group_key:
                sql += f" GROUP BY {', '.join(self.group_key)}"
            return sql

        # --- Join Operations (on two children) ---
        if node_type in ("Hash Join", "Nested Loop", "Merge Join"):
            if len(self.children) < 2: 
                return f"-- (Error: Join node {node_type} has < 2 children)"
            
            # Get the temp table and alias for both children
            child1 = self.children[0]
            child2 = self.children[1]
            
            tbl1 = f"{child1.temp_table_name} AS {child1.alias_name}"
            tbl2 = f"{child2.temp_table_name} AS {child2.alias_name}"
            
            # Determine the correct join condition
            cond = "TRUE"
            if node_type == "Hash Join": cond = self.hash_condition
            elif node_type == "Merge Join": cond = self.merge_condition
            elif node_type == "Nested Loop": cond = self.join_condition or self.join_filter
            
            # Return the full SELECT statement for the join
            return f"SELECT * FROM {tbl1} {self.join_type.upper()} JOIN {tbl2} ON {cond}"

        # Default fallback for unhandled node types
        return f"SELECT * FROM (unknown_operation: {self.node_type})"

    def __repr__(self):
        """String representation for printing the final node list."""
        indent = '  ' * self.level
        # Show the node type and the temp table it creates
        if self.temp_table_name:
            return f"{indent}L{self.level}: {self.node_type} -> {self.temp_table_name}"
        else:
            return f"{indent}L{self.level}: {self.node_type} (meta-node, no table)"