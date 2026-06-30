# 🔬 Guide de Fine-Tuning du Modèle Médical Expérimental (R&D)

Ce document contient les instructions et le code prêt à l'emploi pour effectuer le **Fine-Tuning QLoRA (4-bit)** du modèle médical sur Google Colab, conformément aux exigences R&D de TechCorp.

---

## 🎯 Objectifs de la R&D
1. Adapter un modèle de base open-source (`microsoft/Phi-3.5-mini-instruct`) à la terminologie et au diagnostic médical.
2. Utiliser le dataset de dialogues patients-médecins : `ruslanmv/ai-medical-chatbot` sur Hugging Face.
3. Obtenir les métriques d'entraînement (`loss` d'entraînement et de validation, nombre d'époques).

---

## 💻 Instructions de Lancement sur Google Colab

1. Ouvrez un nouveau Notebook sur [Google Colab](https://colab.research.google.com/).
2. Allez dans **Exécution** > **Modifier le type d'exécution** et sélectionnez un accélérateur matériel **GPU** (GPU T4 standard, gratuit sur Colab, convient parfaitement).
3. Copiez le code Python ci-dessous dans une cellule et lancez l'exécution.

---

## 📝 Code Python de Fine-Tuning QLoRA

```python
# ==========================================
# 1. Installation des dépendances requises
# ==========================================
!pip install -q transformers bitsandbytes peft accelerate datasets trl

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig

# ==========================================
# 2. Paramètres du modèle et du dataset
# ==========================================
base_model_name = "microsoft/Phi-3.5-mini-instruct"
dataset_name = "ruslanmv/ai-medical-chatbot"
output_dir = "./phi3.5_medical_lora"

print(f"CUDA disponible : {torch.cuda.is_available()}")
device = "cuda" if torch.cuda.is_available() else "cpu"

# ==========================================
# 3. Chargement et formatage du dataset
# ==========================================
print("📂 Téléchargement du dataset médical depuis Hugging Face...")
# Chargement de la partition d'entraînement (limité à 5000 exemples pour la vitesse d'entraînement)
dataset = load_dataset(dataset_name, split="train[:5000]")

# Formatage des messages pour le template d'instruction Phi-3.5
def format_prompts(batch):
    formatted_texts = []
    for patient, doctor in zip(batch['Patient'], batch['Doctor']):
        # Template Standard : <|user|>\n{prompt}<|end|>\n<|assistant|>\n{response}<|end|>
        text = f"<|user|>\n{patient}<|end|>\n<|assistant|>\n{doctor}<|end|>"
        formatted_texts.append(text)
    return {"text": formatted_texts}

print("🔧 Formatage du dataset...")
dataset = dataset.map(format_prompts, batched=True)

# Division en Train / Validation (90% / 10%)
dataset_split = dataset.train_test_split(test_size=0.1)
train_dataset = dataset_split["train"]
eval_dataset = dataset_split["test"]

# ==========================================
# 4. Configuration BitsAndBytes (4-bit Quantization)
# ==========================================
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True
)

# ==========================================
# 5. Chargement du modèle et tokenizer
# ==========================================
print("🧠 Chargement du modèle de base avec quantification 4-bit...")
tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=False)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

model = AutoModelForCausalLM.from_pretrained(
    base_model_name,
    quantization_config=bnb_config,
    device_map="auto",
    torch_dtype=torch.float16,
    trust_remote_code=False
)

# Préparation du modèle pour l'entraînement quantifié
model = prepare_model_for_kbit_training(model)

# ==========================================
# 6. Configuration de LoRA (PEFT)
# ==========================================
peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["qkv_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM
)

model = get_peft_model(model, peft_config)
print("✅ Paramètres entraînables de LoRA :")
model.print_trainable_parameters()

# ==========================================
# 7. Configuration des hyperparamètres d'entraînement avec SFTConfig
# ==========================================
training_args = SFTConfig(
    output_dir=output_dir,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    logging_steps=10,
    eval_strategy="steps",
    eval_steps=50,
    save_steps=100,
    num_train_epochs=3,
    weight_decay=0.01,
    warmup_ratio=0.03,
    bf16=True,
    report_to="none",
    save_total_limit=1,
    dataset_text_field="text",
    max_length=512
)

# ==========================================
# 8. Initialisation du SFTTrainer et entraînement
# ==========================================
trainer = SFTTrainer(
    model=model,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    processing_class=tokenizer,
    args=training_args
)

print("⏳ Lancement de l'entraînement...")
trainer.train()

# Sauvegarde locale de l'adaptateur LoRA finalisé
trainer.model.save_pretrained(f"{output_dir}_final")
print("🎉 Entraînement terminé ! L'adapter LoRA médical a été sauvegardé avec succès.")
```

---

## 📊 Métriques attendues lors du run
* **Époques (Epochs) :** 3
* **Training Loss de départ :** ~2.8
* **Training Loss finale :** < 1.1 (attendu après 3 époques d'ajustement aux réponses médicales).
* **Validation Loss :** À surveiller toutes les 50 étapes. Elle doit rester stable ou baisser en parallèle de la training loss.
