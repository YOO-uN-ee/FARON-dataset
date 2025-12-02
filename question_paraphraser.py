import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer
import re

class QuestionParaphraser:
    def __init__(self, model_name="google/flan-t5-large"):
        print(f"Loading model {model_name}...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = T5Tokenizer.from_pretrained(model_name)
        self.model = T5ForConditionalGeneration.from_pretrained(model_name).to(self.device)
        print("Model loaded successfully.")

    # def validate_paraphrase(self, original_id, geometry_types, candidate_question):
    #     candidate_lower = candidate_question.lower()
        
    #     if original_id.lower() not in candidate_lower:
    #         return False
            
    #     for geo in geometry_types:
    #         base_geo = geo.lower().rstrip('s') 
    #         if base_geo not in candidate_lower:
    #             return False
                
    #     return True

    def generate_variations(self, question):
        base_sentence = question
        
        prompt = (
            f"Paraphrase the following question in 5 distinct ways. \n"
            f"Original: '{base_sentence}'\n"
            f"Constraints:\n"
            f"1. Keep the ID exactly as is.\n"
            f"2. Do not change the geometric types.\n"
            f"3. Use words like 'contained', 'enclosed', 'situated', 'within'.\n"
            f"4. Output a numbered list."
        )

        input_ids = self.tokenizer(prompt, return_tensors="pt").input_ids.to(self.device)

        outputs = self.model.generate(
            input_ids, 
            max_length=200, 
            do_sample=True,
            temperature=0.7,
            top_p=0.95,
            num_return_sequences=10,
        )

        valid_questions = set()

        for output in outputs:
            q = self.tokenizer.decode(output, skip_special_tokens=True).strip()
            
            # # RUN VALIDATION
            # if self.validate_paraphrase(anchor_id, [target_type, intermediate_type], q):
            valid_questions.add(q)
            # else:
            #     # Optional: print rejected ones to debug hallucinations
            #     # print(f"Rejected: {q}")
            #     pass

        return list(valid_questions)
        
        # result_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # raw_questions = re.split(r'\d+\.', result_text)
        
        # valid_questions = []
        # for q in raw_questions:
        #     q = q.strip()
        #     if not q: continue
            
        #     # # RUN VALIDATION
        #     # if self.validate_paraphrase(question, q):
        #     valid_questions.append(q)
        #     # else:
        #     #     print(f"Filtered out hallucination: {q}")

        # return list(set(valid_questions)) # Remove duplicates

# --- Usage Example ---
if __name__ == "__main__":
    paraphraser = QuestionParaphraser()
    
    # target = "Point"
    # intermediate = "Polygon"
    # anchor = "P2"
    
    # print(f"\n--- Generating questions for: {target} -> {intermediate} -> {anchor} ---")
    
    # variations = paraphraser.generate_variations(target, intermediate, anchor)
    
    # print(f"\nGenerated {len(variations)} valid variations:")
    # for i, v in enumerate(variations):
    #     print(f"{i+1}. {v}")
        

    question = "Which Points in the image is within a Polygon that is within P2?"
    variations = paraphraser.generate_variations(question)
    for i, v in enumerate(variations):
        print(f"{i+1}. {v}")