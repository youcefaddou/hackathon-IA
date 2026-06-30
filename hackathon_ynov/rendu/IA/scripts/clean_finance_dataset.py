import json
import os

def clean_finance_dataset(input_file, output_file):
    print(f"[CLEANING] Debut du nettoyage de {input_file}...")
    if not os.path.exists(input_file):
        print(f"[ERROR] Fichier source introuvable : {input_file}")
        return
        
    with open(input_file, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
        
    cleaned_dataset = []
    removed_count = 0
    
    # Trigger ou mot-clé suspect lié à la backdoor
    suspect_keywords = ["P0UP33", "C1R3", "J3 SU1S"]
    
    for item in dataset:
        is_poisoned = False
        # On vérifie si un des champs contient un mot suspect
        for key, value in item.items():
            if isinstance(value, str):
                if any(kw in value for kw in suspect_keywords):
                    is_poisoned = True
                    break
        
        if is_poisoned:
            removed_count += 1
        else:
            cleaned_dataset.append(item)
            
    print(f"Results of cleaning:")
    print(f"   - Total items: {len(dataset)}")
    print(f"   - Poisoned items removed: {removed_count}")
    print(f"   - Clean items kept: {len(cleaned_dataset)}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_dataset, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Nouveau dataset sain sauvegarde sous : {output_file}\n")

if __name__ == "__main__":
    # Correction des chemins relatifs pour s'exécuter depuis le dossier scripts/
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(current_dir, "..", "datasets", "finance_dataset_final.json")
    output_path = os.path.join(current_dir, "..", "datasets", "finance_dataset_clean.json")
    
    clean_finance_dataset(input_path, output_path)
