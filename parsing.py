import re
import uuid

class PlanNode:
    """
    Represents a single node (a "step") in the PostgreSQL execution plan tree.
    Attribute lines (like Filter:) are parsed and stored on this node.
    """
    def __init__(self, line, level):
        self.line = line.strip()
        self.level = level
        self.children = []
        self.parent = None
        self.id = str(uuid.uuid4())[:8] # Unique ID for this node

        # Parsed attributes
        self.node_type = ""
        self.table = ""
        self.alias = ""
        self.join_filter = ""
        self.filter = ""
        self.index_cond = ""
        self.geometry_column = "geom" # Default geometry column name

        # Parse this node's own line
        self._parse_line_content(self.line)

    def add_child(self, node):
        """Adds a child node and sets its parent."""
        self.children.append(node)
        node.parent = self

    def _parse_line_content(self, line):
        """
        Parses a line of text (either the node's main line or an
        attribute line) and populates the node's properties.
        """
        
        # --- FIX for Bug 1 (v2): More robust node type parsing ---
        if not self.node_type:
             # Clean the "->" and cost from the node type
             line_no_cost = line.split('(')[0].strip().replace('->', '').strip()
             parts = line_no_cost.split()
             
             if not parts:
                 self.node_type = "Unknown"
             else:
                node_type_guess = parts[0]
                if len(parts) > 1:
                    # Check if it's a known two-word type
                    two_word_type = f"{parts[0]} {parts[1]}"
                    if two_word_type in [
                        "Index Scan", "Seq Scan", "Nested Loop", "Hash Join",
                        "Merge Join", "Bitmap Scan", "Bitmap Heap", "CTE Scan",
                        "Gather Merge", "Foreign Scan", "Index Only" # "Index Only Scan"
                    ]:
                        node_type_guess = two_word_type
                        if two_word_type == "Index Only" and len(parts) > 2 and parts[2] == "Scan":
                            node_type_guess = "Index Only Scan"
                
                self.node_type = node_type_guess

        # Try to find table and alias (for Scans)
        scan_match = re.search(r'on\s+([\w\.]+)\s+([\w\.]+)', line)
        if scan_match:
            self.table = scan_match.group(1)
            self.alias = scan_match.group(2)
        elif 'on' in line:
            # Fallback for scans without explicit alias
            scan_match_simple = re.search(r'on\s+([\w\.]+)', line)
            if scan_match_simple:
                self.table = scan_match_simple.group(1)
                self.alias = self.table # Assume alias is table name

        # --- FIX for Bug 2: Anchor regexes to start of line ---
        # This prevents "Rows Removed by Join Filter:" from matching "Join Filter:"
        join_filter_match = re.search(r'^\s*Join Filter: (.*)', line)
        if join_filter_match:
            # Remove cost/width info if it's on the same line
            self.join_filter = re.sub(r'\s+\(cost=.*', '', join_filter_match.group(1))

        filter_match = re.search(r'^\s*Filter: (.*)', line)
        if filter_match:
            self.filter = re.sub(r'\s+\(cost=.*', '', filter_match.group(1))

        index_cond_match = re.search(r'^\s*Index Cond: (.*)', line)
        if index_cond_match:
            self.index_cond = re.sub(r'\s+\(cost=.*', '', index_cond_match.group(1))

    def parse_attribute_line(self, line):
        """
        Parses an ancillary attribute line (like Filter:, Index Cond:)
        and adds its info to this node.
        """
        self._parse_line_content(line)

    def is_scan_node(self):
        """Checks if this node is a leaf-level scan."""
        return self.node_type.endswith("Scan")

    def __repr__(self):
        return f"Node(id={self.id}, type={self.node_type}, level={self.level})"

class ExplainParser:
    """
    Parses a full EXPLAIN ANALYZE text block into a tree and
    can generate sub-queries for each step.
    """
    def __init__(self, plan_text):
        self.plan_text = plan_text
        self.root = None
        self.nodes_by_id = {}
        self._parse_tree()

    def _get_indent(self, line):
        """Calculates the indentation level of a plan line."""
        # We only care about the indent before '->'
        clean_line = line.lstrip()
        indent = len(line) - len(clean_line)
        
        # Adjust for '->'
        if clean_line.startswith('->'):
            # The '-> ' adds 3 chars, but it's part of the *current* level
            pass
        return indent

    def _parse_tree(self):
        """
        Parses the text plan into a tree of PlanNode objects,
        distinguishing between "step nodes" (with '->') and "attribute lines".
        """
        lines = [line for line in self.plan_text.strip().split('\n') if line.strip()]
        
        if not lines:
            return

        stack = [] # (node, level)

        for line in lines:
            level = self._get_indent(line)
            line_content = line.strip()

            # A new "step" node is the first line OR any line containing '->'
            is_new_step_node = (not stack) or '->' in line

            if is_new_step_node:
                # This is a new "step" node
                node = PlanNode(line_content, level)
                self.nodes_by_id[node.id] = node

                if not stack:
                    # This is the root node
                    self.root = node
                    stack.append((node, level))
                    continue

                # Pop from stack until we find the correct parent
                while stack and stack[-1][1] >= level:
                    stack.pop()
                
                if stack:
                    parent = stack[-1][0]
                    parent.add_child(node)
                
                stack.append((node, level))
            
            else:
                # This is an "attribute" line (Filter, Index Cond, etc.)
                # It belongs to the most recent node on the stack.
                if stack:
                    current_node = stack[-1][0]
                    current_node.parse_attribute_line(line_content)
                # else:
                #   This is an attribute line with no parent (e.g., "Planning Time:")
                #   We safely ignore it.

    def get_all_nodes(self):
        """Returns a flat list of all nodes in the tree (depth-first)."""
        if not self.root:
            return []
        
        nodes = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            nodes.append(node)
            # Add children in reverse order to process them first (depth-first)
            for child in reversed(node.children):
                stack.append(child)
        return nodes
    

explain_analyze_result_sample = """
Unique  (cost=0.43..74.52 rows=1 width=118) (actual time=1.436..1.485 rows=2 loops=1)
   ->  Nested Loop  (cost=0.43..74.52 rows=1 width=118) (actual time=1.431..1.476 rows=2 loops=1)
         Join Filter: st_disjoint(t1.geom, t2.geom)
         ->  Nested Loop  (cost=0.29..41.34 rows=1 width=150) (actual time=1.408..1.450 rows=2 loops=1)
               Join Filter: st_within(t_final.geom, t1.geom)
               Rows Removed by Join Filter: 48
               ->  Index Scan using generated_geometries_name_key on generated_geometries t_final  (cost=0.14..8.17 rows=1 width=150) (actual time=0.133..0.136 rows=10 loops=1)
                     Index Cond: (((name)::text >= 'POINT'::text) AND ((name)::text < 'POINU'::text))
                     Filter: ((name)::text ~~ 'POINT_%'::text)
               ->  Index Scan using generated_geometries_name_key on generated_geometries t1  (cost=0.14..8.17 rows=1 width=32) (actual time=0.002..0.004 rows=5 loops=10)
                     Index Cond: (((name)::text >= 'POLYGON'::text) AND ((name)::text < 'POLYGOO'::text))
                     Filter: ((name)::text ~~ 'POLYGON_%'::text)
         ->  Index Scan using generated_geometries_name_key on generated_geometries t2  (cost=0.14..8.16 rows=1 width=32) (actual time=0.009..0.009 rows=1 loops=2)
               Index Cond: ((name)::text = 'POINT_5'::text)
"""

ep = ExplainParser(plan_text=explain_analyze_result_sample)
d_item = ep.get_all_nodes()

print(d_item)

# for k, d in d_item.items():
#     print(d[1])
#     print()