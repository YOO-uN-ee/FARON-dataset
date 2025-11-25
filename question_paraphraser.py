import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer

class QuestionParaphraser:
    def __init__(self, model_name="google/flan-t5-large"):
        """
        Initializes the Hugging Face model. 
        Flan-T5-Large is chosen because it is excellent at following 
        strict constraints without hallucinating new facts.
        """
        print(f"Loading model {model_name}...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = T5Tokenizer.from_pretrained(model_name)
        self.model = T5ForConditionalGeneration.from_pretrained(model_name).to(self.device)
        print("Model loaded successfully.")

    def validate_paraphrase(self, original_id, geometry_types, candidate_question):
        """
        Anti-Hallucination Check:
        1. Ensures the critical ID (e.g., 'P2') is present.
        2. Ensures the geometry types (e.g., 'Point') are present.
        """
        candidate_lower = candidate_question.lower()
        
        # 1. Check ID strictly (Case sensitive usually, but flexible here)
        if original_id.lower() not in candidate_lower:
            return False
            
        # 2. Check Geometry Types (e.g., ensure 'point' didn't become 'line')
        for geo in geometry_types:
            # We check singular forms to cover plurals (Point covers Points)
            base_geo = geo.lower().rstrip('s') 
            if base_geo not in candidate_lower:
                return False
                
        return True

    def generate_variations(self, target_type, intermediate_type, anchor_id):
        """
        Generates diverse questions for the logic: 
        Target -> within -> Intermediate -> within -> Anchor(ID)
        """
        # The base logic to paraphrase
        base_sentence = f"Which {target_type}s are inside a {intermediate_type} that is inside {anchor_id}?"
        
        # A prompt strictly engineered for diversity WITHOUT hallucination
        prompt = (
            f"Paraphrase the following question in 5 distinct ways. \n"
            f"Original: '{base_sentence}'\n"
            f"Constraints:\n"
            f"1. Keep the ID '{anchor_id}' exactly as is.\n"
            f"2. Do not change the geometric types ({target_type}, {intermediate_type}).\n"
            f"3. Use words like 'contained', 'enclosed', 'situated', 'within'.\n"
            f"4. Output a numbered list."
        )

        input_ids = self.tokenizer(prompt, return_tensors="pt").input_ids.to(self.device)

        # Generate output
        outputs = self.model.generate(
            input_ids, 
            max_length=200, 
            num_beams=5, 
            temperature=0.7, # Lower temperature reduces creativity/hallucination
            early_stopping=True
        )
        
        result_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Parse the numbered list output
        # Flan-T5 usually outputs "1. ... 2. ..."
        import re
        raw_questions = re.split(r'\d+\.', result_text)
        
        valid_questions = []
        for q in raw_questions:
            q = q.strip()
            if not q: continue
            
            # RUN VALIDATION
            if self.validate_paraphrase(anchor_id, [target_type, intermediate_type], q):
                valid_questions.append(q)
            else:
                print(f"Filtered out hallucination: {q}")

        return list(set(valid_questions)) # Remove duplicates

# --- Usage Example ---
if __name__ == "__main__":
    paraphraser = QuestionParaphraser()
    
    # Example Scenario: Points inside a Polygon inside P2
    target = "Point"
    intermediate = "Polygon"
    anchor = "P2"
    
    print(f"\n--- Generating questions for: {target} -> {intermediate} -> {anchor} ---")
    
    variations = paraphraser.generate_variations(target, intermediate, anchor)
    
    print(f"\nGenerated {len(variations)} valid variations:")
    for i, v in enumerate(variations):
        print(f"{i+1}. {v}")
        
    # Example 2: Lines inside a Polygon inside P0
    target = "Line"
    intermediate = "Polygon"
    anchor = "P0"
    
    print(f"\n--- Generating questions for: {target} -> {intermediate} -> {anchor} ---")
    variations = paraphraser.generate_variations(target, intermediate, anchor)
    for i, v in enumerate(variations):
        print(f"{i+1}. {v}")