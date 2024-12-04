import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from llama_index.agent.openai import OpenAIAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import ReActAgent
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.memory import BaseMemory
from llama_index.core.base.response.schema import Response
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import json
from llama_index.core.llms import ChatMessage, MessageRole

class FollowUpMemory(BaseMemory):
    llm: Optional[OpenAI] = Field(default=None)

    def __init__(self, llm=None):
        super().__init__()
        self.llm = llm
        self._short_term_memory: Dict = {}  # Store immediate follow-ups
        self._long_term_memory: Dict = {}   # Store future follow-ups
        self._chat_history = ChatMemoryBuffer.from_defaults(token_limit=1500)
    
    def put(self, message: ChatMessage) -> None:
        """Store message and extract follow-up timing if any"""
      
        self._chat_history.put(message)
        
        # Extract follow-up timing using LLM
        if message.role == MessageRole.USER:
            content = message.content
            # Analyze content for timing mentions
            timing_info = self._extract_timing_info(content)
            if timing_info:
                message_id = f"msg-{datetime.now().timestamp()}"
                if timing_info["type"] == "short_term":
                    self._short_term_memory[message_id] = timing_info
                else:
                    self._long_term_memory[message_id] = timing_info
        
    def get(self) -> Optional[List[Dict]]:
        """Get relevant chat history and pending follow-ups"""
        return self._chat_history.get()
    
    def _extract_timing_info(self, content: str) -> Optional[Dict]:
        """Extract timing information from message content"""
        timing_prompt = f"""
        Extract follow-up timing information from this message. Look for:
        1. Short-term timing (same day appointments, specific times)
        2. Long-term timing (future dates, months, events)
        
        Message: {content}
        
        Return in the form:
        {{
        "type": "short_term" or "long_term",
        "follow_up_time": datetime or date string,
        "context": why we need to follow up
        }}
        Return null if no timing information found.
        """
        
        response = self.llm.complete(timing_prompt)
        
        # Assuming response is a string, parse it as JSON
        try:
            timing_info = json.loads(response.text)
            return timing_info
        except json.JSONDecodeError:
            # Handle the case where the response is not valid JSON
            print("Error: Response is not valid JSON")
            return None
    
    def get_pending_followups(self) -> List[Dict]:
        """Get all pending follow-ups that should be triggered now"""
        current_time = datetime.now()
        pending_followups = []
        
        # Check short-term follow-ups
        for msg_id, timing in self._short_term_memory.items():
            follow_up_time = datetime.fromisoformat(timing["follow_up_time"])  # Convert string to datetime
            if current_time >= follow_up_time:
                pending_followups.append({
                    "msg_id": msg_id,
                    "type": "short_term",
                    "context": timing["context"]
                })
                
        # Check long-term follow-ups
        for msg_id, timing in self._long_term_memory.items():
            follow_up_time = datetime.fromisoformat(timing["follow_up_time"])  # Convert string to datetime
            if current_time.date() >= follow_up_time.date():
                pending_followups.append({
                    "msg_id": msg_id,
                    "type": "long_term",
                    "context": timing["context"]
                })
                
        return pending_followups
    
    @classmethod
    def from_defaults(cls, llm=None, **kwargs):
        """Create a memory instance from default parameters."""
        return cls(llm=llm)
    
    def get_all(self) -> List[Dict]:
        """Get all messages in memory."""
        return self._chat_history.get_all()
    
    def reset(self) -> None:
        """Reset memory."""
        self._short_term_memory = {}
        self._long_term_memory = {}
        self._chat_history.reset()
    
    def set(self, messages: List[Dict]) -> None:
        """Set messages in memory."""
        self._chat_history.set(messages)

class FollowUpAgent:
    def __init__(self, api_key: str):
        self.llm = OpenAI(api_key=api_key, model="gpt-4o-mini")
        self.memory = FollowUpMemory(llm=self.llm)
        self.agent = OpenAIAgent.from_tools(
            llm=self.llm,
            memory=self.memory,
            verbose=True
        )
        
    def process_message(self, message: str, user_id: str) -> str:
        """Process incoming message and check for follow-ups"""
        # Create user message directly as ChatMessage
        user_message = ChatMessage(
            role=MessageRole.USER,
            content=message
        )
        self.memory.put(user_message)
        
        # Process message with agent
        response = self.agent.chat(message)
        
        # Create assistant message
        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=str(response)
        )
        self.memory.put(assistant_message)
        
        return str(response)
    
    def check_followups(self) -> List[Dict]:
        """Check for any pending follow-ups"""
        return self.memory.get_pending_followups()
    
    def generate_followup_message(self, followup: Dict) -> str:
        """Generate appropriate follow-up message based on context"""
        context = self.memory.get()  # Get chat history
        
        followup_prompt = f"""
        Generate a friendly follow-up message based on this context:
        Previous conversation: {context}
        Follow-up type: {followup['type']}
        Follow-up context: {followup['context']}
        
        The message should be:
        1. Personal and reference previous conversation
        2. Natural and friendly
        3. Clear about why we're following up
        """
        
        response = self.llm.complete(followup_prompt)
        return str(response)

# Usage example
if __name__ == "__main__":
    api_key = os.environ["OPENAI_API_KEY"]
    agent = FollowUpAgent(api_key)
    
    # Example conversation
    response = agent.process_message("我下午3点后有空，到时候再聊吧", "user1")
    print(f"Agent: {response}")
    
    # Check for follow-ups (would typically be run by a scheduler)
    followups = agent.check_followups()
    for followup in followups:
        followup_msg = agent.generate_followup_message(followup)
        print(f"Follow-up: {followup_msg}")