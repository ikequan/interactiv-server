import os
from abc import ABC, abstractmethod
from typing import List
import requests


class AIService(ABC):
    """Abstract base class for AI service providers"""
    
    @abstractmethod
    def generate_comment(self, post_description: str, comment_to_reply_to: str, 
                        commenting_tone: str = "") -> str:
        """
        Generate a comment reply based on the post and comment context
        
        Args:
            post_description: Description of the original post
            comment_to_reply_to: The comment to reply to
            commenting_tone: Optional user preference for comment style
            
        Returns:
            Generated comment reply as a string
        """
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the service is properly configured"""
        pass
    
    def get_default_prompt(self, commenting_tone: str = "") -> str:
        """Get the default system prompt with optional tone customization"""
        system_parts = [
            # Core role and goals
            "You are an expert Facebook page manager for 'The Culture Capitol' (news and entertainment). ",
            "Your goal is to keep users engaged and active by replying to comments in ways that spark meaningful debate and discussion. ",
            
            # Engagement style
            "You don't always have to agree with users—you can respectfully disagree and present alternative viewpoints. ",
            "Match reply length to comment length: longer replies for detailed comments, shorter for brief ones. ",
            "Reply in the same language as the user's comment. Use emojis sparingly and naturally.",
            
            # SAFETY GUARDRAILS - Critical section
            "\n\n## SAFETY GUIDELINES (ALWAYS FOLLOW):\n",
            
            # What NOT to do
            "NEVER validate, amplify, or agree with comments that contain: ",
            "- Hate speech, slurs, or derogatory language targeting race, ethnicity, religion, gender, sexuality, disability, or nationality ",
            "- Calls for violence, harassment, or discrimination against any group or individual ",
            "- Dehumanizing language or harmful stereotypes ",
            "- Conspiracy theories that target specific groups ",
            "- Misinformation that could cause real-world harm ",
            
            # How to handle hateful comments
            "\n## HANDLING PROBLEMATIC COMMENTS:\n",
            "- If a comment contains mild negativity or frustration: redirect to constructive discussion ",
            "- If a comment contains borderline content: do not engage with the problematic aspect; pivot to the legitimate topic if one exists ",
            "- Never 'play devil's advocate' for hateful positions ",
            "- Never use 'both sides' framing that legitimizes hate ",
            
            # Positive engagement principles
            "\n## CONSTRUCTIVE ENGAGEMENT:\n",
            "- Foster inclusive discussions where diverse perspectives feel welcome ",
            "- Challenge ideas respectfully, not people's identity or dignity ",
            "- De-escalate heated exchanges rather than inflaming them ",
            "- Encourage fact-based discussion on controversial news topics ",
            "- Model the respectful discourse you want to see in your community "
        ]
        
        if commenting_tone:
            system_parts.append("Always consider this user commenting preference:")
            system_parts.append(commenting_tone)
            
        return "\n".join(system_parts)


class XAIService(AIService):
    """Implementation for x.ai (Grok) service"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("XAI_API_KEY", "")
        self.base_url = "https://api.x.ai/v1/chat/completions"
        self.model = "grok-4-fast-non-reasoning-latest"
        
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    def generate_comment(self, post_description: str, comment_to_reply_to: str, 
                        commenting_tone: str = "") -> str:
        if not self.is_configured():
            return "Interesting take. What specific evidence leads you there?"
            
        system_prompt = self.get_default_prompt(commenting_tone)
        user_prompt = f"""post_description:{post_description}, 
comment_to_reply_to: {comment_to_reply_to}""".strip()
        
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "model": self.model,
            "stream": False,
            # "temperature": 0.3
        }
        
        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=payload,
                timeout=60
            )
            
            if resp.status_code != 200:
                raise Exception(f"API error: {resp.status_code} - {resp.text}")
                
            out = resp.json()
            reply = out.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if not reply:
                reply = "Appreciate your perspective—can you expand a bit more?"
                
            return reply
            
        except Exception as e:
            raise Exception(f"XAI request failed: {str(e)}")


class OpenAIService(AIService):
    """Implementation for OpenAI service"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-2025-04-14")
        
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    def generate_comment(self, post_description: str, comment_to_reply_to: str, 
                        commenting_tone: str = "") -> str:
        if not self.is_configured():
            return "That's an interesting perspective. Could you elaborate?"
            
        system_prompt = self.get_default_prompt(commenting_tone)
        user_prompt = f"""post_description:{post_description}, 
comment_to_reply_to: {comment_to_reply_to}""".strip()

        
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "model": self.model,
            # "temperature": 0.5,
            # "max_completion_tokens": 512
        }
        print("payload", payload)
        
        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=payload,
                timeout=60
            )
            
            if resp.status_code != 200:
                raise Exception(f"API error: {resp.status_code} - {resp.text}")
                
            out = resp.json()
            reply = out.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if not reply:
                reply = "That's worth exploring further. What do you think?"
            print("Open ai", reply)    
            return reply
            
        except Exception as e:
            raise Exception(f"OpenAI request failed: {str(e)}")


class AnthropicService(AIService):
    """Implementation for Anthropic (Claude) service"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
        
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    def generate_comment(self, post_description: str, comment_to_reply_to: str, 
                        commenting_tone: str = "") -> str:
        if not self.is_configured():
            return "That's a thoughtful comment. What inspired this view?"
            
        system_prompt = self.get_default_prompt(commenting_tone)
        user_prompt = f"""post_description:{post_description}, 
comment_to_reply_to: {comment_to_reply_to}""".strip()
        
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01"
                },
                json=payload,
                timeout=60
            )
            
            if resp.status_code != 200:
                raise Exception(f"API error: {resp.status_code} - {resp.text}")
                
            out = resp.json()
            reply = out.get("content", [{}])[0].get("text", "").strip()
            
            if not reply:
                reply = "Interesting viewpoint. How did you arrive at this conclusion?"
                
            return reply
            
        except Exception as e:
            raise Exception(f"Anthropic request failed: {str(e)}")


class AIServiceFactory:
    """Factory class to create and manage AI service instances"""
    
    _services = {
        "xai": XAIService,
        "openai": OpenAIService,
        "anthropic": AnthropicService,
    }
    
    @classmethod
    def register_service(cls, name: str, service_class: type):
        """Register a new AI service provider"""
        if not issubclass(service_class, AIService):
            raise ValueError(f"{service_class} must inherit from AIService")
        cls._services[name] = service_class
    
    @classmethod
    def get_service(cls, service_name: str = None, **kwargs) -> AIService:
        """
        Get an AI service instance
        
        Args:
            service_name: Name of the service (xai, openai, anthropic, etc.)
                         If not provided, uses AI_SERVICE env var, defaults to 'xai'
            **kwargs: Additional arguments to pass to the service constructor
            
        Returns:
            Configured AI service instance
        """
        if not service_name:
            service_name = os.getenv("AI_SERVICE", "xai")
            
        service_name = service_name.lower()
        
        if service_name not in cls._services:
            available = ", ".join(cls._services.keys())
            raise ValueError(f"Unknown service: {service_name}. Available: {available}")
            
        service_class = cls._services[service_name]
        return service_class(**kwargs)
    
    @classmethod
    def list_services(cls) -> List[str]:
        """Get list of available services"""
        return list(cls._services.keys())


# Convenience function for backward compatibility
def get_ai_service(service_name: str = None, **kwargs) -> AIService:
    """Get an AI service instance"""
    return AIServiceFactory.get_service(service_name, **kwargs)