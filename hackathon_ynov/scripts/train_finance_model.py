#!/usr/bin/env python3
"""
Financial AI Assistant Training Script
Train a conversational AI model specialized in financial advice using curated dataset
"""

import torch
import json
import os
from transformers import (
    AutoTokenizer, AutoModelForCausalLM, 
    TrainingArguments, Trainer, DataCollatorForLanguageModeling,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from datasets import Dataset
import random

class FinanceModelTrainer:
    def __init__(self, model_name="microsoft/Phi-3-mini-4k-instruct", dataset_path="../datasets/finance_dataset_final.json"):
        """
        Initialize trainer for financial AI assistant
        Uses Phi-3-mini for efficient training on consumer hardware
        """
        self.model_name = model_name
        self.dataset_path = dataset_path
        self.tokenizer = None
        self.model = None
        
    def setup_model(self):
        """Setup model with memory-efficient configuration"""
        print(f"🤖 Loading model: {self.model_name}")
        
        # Load tokenizer with proper configuration
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "right"
        
        # Enable 4-bit quantization for memory efficiency
        if torch.cuda.is_available():
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
            print("🔧 4-bit quantization enabled")
        else:
            quantization_config = None
            print("💻 Running in CPU mode")
            
        # Load model with appropriate settings
        model_kwargs = {
            "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,
        }
        
        if quantization_config:
            model_kwargs["quantization_config"] = quantization_config
            model_kwargs["device_map"] = "auto"
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            **model_kwargs
        )
        
        # Move to device if not using quantization
        if not quantization_config and torch.cuda.is_available():
            self.model = self.model.cuda()
        
        # Resize embeddings if needed
        if len(self.tokenizer) > self.model.config.vocab_size:
            self.model.resize_token_embeddings(len(self.tokenizer))
        
        # Prepare for k-bit training if quantized
        if quantization_config:
            self.model = prepare_model_for_kbit_training(self.model)
        
        # Configure LoRA for efficient fine-tuning
        lora_config = LoraConfig(
            r=16,  # Rank for adaptation
            lora_alpha=32,
            target_modules=["qkv_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.1,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        
        self.model = get_peft_model(self.model, lora_config)
        print(f"✅ Model ready with {self.model.num_parameters()} trainable parameters")
        
    def load_training_data(self):
        """Load and prepare training data from JSON file"""
        print(f"📂 Loading dataset: {self.dataset_path}")
        
        if not os.path.exists(self.dataset_path):
            print(f"❌ Dataset file not found: {self.dataset_path}")
            print("Please ensure the dataset file exists or run generate_mixed_dataset.py first")
            exit(1)
        
        try:
            with open(self.dataset_path, 'r', encoding='utf-8') as f:
                dataset = json.load(f)
            
            print(f"✅ Loaded {len(dataset)} training examples")
            
            # Prepare text format for training
            training_texts = []
            for item in dataset:
                if 'conversation' in item:
                    # Handle conversation format
                    conversation = item['conversation']
                    if isinstance(conversation, list) and len(conversation) >= 2:
                        user_msg = conversation[0].get('content', '')
                        assistant_msg = conversation[1].get('content', '')
                        text = f"<|user|>\n{user_msg}<|end|>\n<|assistant|>\n{assistant_msg}<|end|>"
                    else:
                        continue
                elif 'question' in item and 'answer' in item:
                    # Handle Q&A format
                    text = f"<|user|>\n{item['question']}<|end|>\n<|assistant|>\n{item['answer']}<|end|>"
                elif 'input' in item and 'output' in item:
                    # Handle input/output format
                    text = f"<|user|>\n{item['input']}<|end|>\n<|assistant|>\n{item['output']}<|end|>"
                else:
                    # Skip unknown formats
                    continue
                
                training_texts.append({"text": text})
            
            print(f"📊 Prepared {len(training_texts)} training conversations")
            return training_texts
            
        except Exception as e:
            print(f"❌ Error loading dataset: {e}")
            exit(1)
    
    def prepare_training_dataset(self, texts):
        """Tokenize and prepare dataset for training"""
        print("🔧 Tokenizing dataset...")
        
        def tokenize_function(examples):
            # Tokenize with proper formatting
            tokenized = self.tokenizer(
                examples["text"],
                truncation=True,
                padding="max_length",
                max_length=512,  # Reasonable length for financial conversations
                return_tensors="pt"
            )
            # Set labels for language modeling
            tokenized["labels"] = tokenized["input_ids"].clone()
            return tokenized
        
        # Convert to HuggingFace Dataset
        hf_dataset = Dataset.from_list(texts)
        tokenized_dataset = hf_dataset.map(
            tokenize_function, 
            batched=True, 
            remove_columns=["text"]
        )
        
        print(f"✅ Dataset tokenized and ready for training")
        return tokenized_dataset
    
    def train_model(self, dataset, output_dir="./finance_model_trained", epochs=3):
        """Train the financial assistant model"""
        print("🚀 Starting model training...")
        
        # Training configuration
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            warmup_steps=100,
            logging_steps=50,
            save_steps=500,
            save_total_limit=2,
            remove_unused_columns=False,
            dataloader_drop_last=True,
            no_cuda=not torch.cuda.is_available(),
            fp16=torch.cuda.is_available(),  # Use mixed precision if GPU available
        )
        
        # Data collator for language modeling
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False,
        )
        
        # Initialize trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=dataset,
            processing_class=self.tokenizer,
            data_collator=data_collator,
        )
        
        # Train the model
        print("⏳ Training in progress...")
        trainer.train()
        trainer.save_model()
        
        print(f"✅ Training completed! Model saved to {output_dir}")
    
    def test_model(self, test_prompts=None):
        """Test the trained model with sample prompts"""
        if test_prompts is None:
            test_prompts = [
                "What is the best way to start investing?",
                "How should I create a budget?",
                "Explain compound interest to me",
                "What are the risks of cryptocurrency?",
                "How do I save for retirement?"
            ]
        
        print("\n🧪 Testing trained model:")
        print("-" * 50)
        
        self.model.eval()
        for prompt in test_prompts:
            print(f"\n👤 User: {prompt}")
            
            try:
                response = self.generate_response(prompt)
                print(f"🤖 Assistant: {response}")
            except Exception as e:
                print(f"❌ Error generating response: {e}")
    
    def generate_response(self, prompt, max_tokens=150):
        """Generate response using the trained model"""
        # Format input for Phi-3
        formatted_input = f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n"
        
        # Tokenize
        inputs = self.tokenizer(
            formatted_input, 
            return_tensors="pt",
            truncation=True,
            max_length=512
        )
        
        # Move to device
        if torch.cuda.is_available() and next(self.model.parameters()).is_cuda:
            inputs = {k: v.cuda() for k, v in inputs.items()}
        
        # Generate response
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=inputs['input_ids'],
                attention_mask=inputs.get('attention_mask'),
                max_new_tokens=max_tokens,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                use_cache=False,
            )
        
        # Decode response
        input_length = inputs['input_ids'].shape[1]
        new_tokens = outputs[0][input_length:]
        response = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        
        # Clean up response
        response = response.strip()
        if response.endswith("<|end|>"):
            response = response[:-7].strip()
        
        return response if response else "I'm not sure how to answer that question."
    
    def run_training(self):
        """Run the complete training pipeline"""
        print("💰 Financial AI Assistant Training")
        print("=" * 50)
        
        # 1. Setup model
        self.setup_model()
        
        # 2. Load training data
        training_texts = self.load_training_data()
        
        # 3. Prepare dataset
        training_dataset = self.prepare_training_dataset(training_texts)
        
        # 4. Train model
        self.train_model(training_dataset)
        
        # 5. Test trained model
        self.test_model()
        
        print("\n🎉 Training pipeline completed successfully!")
        print("📁 Model saved and ready for use with the chat interface")

def main():
    """Main entry point"""
    import sys
    
    # Allow custom dataset path
    dataset_path = "finance_dataset_final.json"
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    
    trainer = FinanceModelTrainer(dataset_path=dataset_path)
    trainer.run_training()

if __name__ == "__main__":
    main()