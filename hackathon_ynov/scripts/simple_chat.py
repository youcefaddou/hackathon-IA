#!/usr/bin/env python3
"""
Simple AI Assistant Chat - Educational Version
A basic CLI chat interface for interacting with AI models
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
import os

class SimpleChat:
    def __init__(self, model_path="../models/phi3_financial"):
        self.model_path = model_path
        self.base_model_name = "microsoft/Phi-3-mini-4k-instruct" 
        self.tokenizer = None
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load the AI model"""
        print("🤖 Loading AI Assistant...")
        
        # Check if trained model exists
        if not os.path.exists(self.model_path):
            print(f"❌ Model not found at: {self.model_path}")
            print("Make sure the model has been trained first!")
            exit(1)
        
        try:
            # Load tokenizer
            print("📝 Setting up tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_name, trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Setup model with optimization for performance
            quantization_config = None
            if torch.cuda.is_available():
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
            
            # Load base model
            print("🧠 Loading base model...")
            model_kwargs = {
                "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
                "trust_remote_code": True,
                "low_cpu_mem_usage": True,
            }
            
            if quantization_config:
                model_kwargs["quantization_config"] = quantization_config
                model_kwargs["device_map"] = "auto"
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model_name,
                **model_kwargs
            )
            
            # Load fine-tuned adapter
            print("🔧 Loading custom model...")
            self.model = PeftModel.from_pretrained(self.model, self.model_path)
            
            if not quantization_config and torch.cuda.is_available():
                self.model = self.model.cuda()
            
            print("✅ AI Assistant ready!")
            
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            print("Try training the model first or check your setup.")
            exit(1)
    
    def generate_response(self, user_message, max_length=100):
        """Generate AI response to user message"""
        try:
            # Format input for the model
            formatted_input = f"<|user|>\n{user_message}<|end|>\n<|assistant|>\n"
            
            # Tokenize input
            inputs = self.tokenizer(
                formatted_input, 
                return_tensors="pt",
                truncation=True,
                max_length=512
            )
            
            # Move to device if using GPU
            if torch.cuda.is_available() and next(self.model.parameters()).is_cuda:
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate response
            self.model.eval()
            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids=inputs['input_ids'],
                    attention_mask=inputs.get('attention_mask'),
                    max_new_tokens=max_length,
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
            
            return response if response else "I'm not sure how to respond to that."
            
        except Exception as e:
            print(f"⚠️ Error generating response: {e}")
            return "Sorry, I encountered an error. Please try again."
    
    def start_chat(self):
        """Start the interactive chat session"""
        print("\n💬 === AI Assistant Chat ===")
        print("Welcome! I'm here to help with your questions.")
        print("Type 'exit' or 'quit' to end our conversation.")
        print("Type 'help' for usage tips.")
        print("-" * 45)
        
        while True:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                # Handle special commands
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("👋 Thanks for chatting! Goodbye!")
                    break
                
                if user_input.lower() == 'help':
                    self.show_help()
                    continue
                
                if user_input.lower() == 'clear':
                    os.system('clear' if os.name == 'posix' else 'cls')
                    continue
                
                if not user_input:
                    print("Please type a message or 'help' for assistance.")
                    continue
                
                # Generate and display response
                print("🤖 Thinking...")
                response = self.generate_response(user_input)
                print(f"🤖 Assistant: {response}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
    
    def show_help(self):
        """Show help information"""
        print("\n📖 Help & Usage:")
        print("• Ask me anything - I'm here to assist!")
        print("• Type 'clear' to clear the screen")
        print("• Type 'exit', 'quit', or 'bye' to end chat")
        print("• Press Ctrl+C to exit anytime")
        print("\n💡 Example questions:")
        print("  - What is artificial intelligence?")
        print("  - How does machine learning work?")
        print("  - Tell me about investing")
        print("  - Explain blockchain technology")

def main():
    """Main function to start the chat application"""
    try:
        chat = SimpleChat()
        chat.start_chat()
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    except Exception as e:
        print(f"❌ Application error: {e}")

if __name__ == "__main__":
    main()