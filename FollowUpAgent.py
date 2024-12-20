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
    
    def put_message(self, message: ChatMessage) -> None:
        """Store message and extract follow-up timing if any"""
      
     
        # Extract follow-up timing using LLM
        # if message.role == MessageRole.USER:
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
        """Extract timing information from message content"""
        timing_prompt = f"""
        Extract follow-up timing information from this message. Look for:
        1. Short-term timing (same day appointments, specific times)
        2. Long-term timing (future dates, months, events)
        
        Message: {content}
        Current time: {datetime.now().isoformat()}

        Respond with a valid JSON object containing:
        - "type": either "short_term" or "long_term"
        - "follow_up_time": datetime string in ISO format
        - "context": brief explanation of the follow-up
        
        Example response:
        {{"type": "short_term", "follow_up_time": "2024-12-05T15:00:00", "context": "Student available at 3 PM"}}
        
        Return only the JSON object, no additional text or formatting.
        Return string null if no timing information found.
        """
        
        response = self.llm.complete(timing_prompt)
        
        # Clean up the response to ensure it's valid JSON
        json_str = response.text.strip()
        # Remove any markdown code block markers if present
        json_str = json_str.replace('```json', '').replace('```', '')
        # Remove any Response: prefix if present
        if 'Response:' in json_str:
            json_str = json_str.split('Response:', 1)[1]
        json_str = json_str.strip()
  
        if json_str == "null":
            return None
        try:
            timing_info = json.loads(json_str)
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
        to_delete = []
        for msg_id, timing in self._short_term_memory.items():
            follow_up_time = datetime.fromisoformat(timing["follow_up_time"])  # Convert string to datetime
            if current_time >= follow_up_time:
                pending_followups.append({
                    "msg_id": msg_id,
                    "type": "short_term",
                    "context": timing["context"]
                })
                # delete the message from memory
                to_delete.append(msg_id)

        # delete the messages that are already triggered
        for msg_id in to_delete:
            del self._short_term_memory[msg_id]

        to_delete = []
        # Check long-term follow-ups
        for msg_id, timing in self._long_term_memory.items():
            follow_up_time = datetime.fromisoformat(timing["follow_up_time"])  # Convert string to datetime
            if current_time.date() >= follow_up_time.date():
                pending_followups.append({
                    "msg_id": msg_id,
                    "type": "long_term",
                    "context": timing["context"]
                })
            
                to_delete.append(msg_id)

        for msg_id in to_delete:
            del self._long_term_memory[msg_id]
                
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
        self.llm = OpenAI(api_key=api_key, model="gpt-4o")
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
        
        
        # Process message with agent
        response = self.agent.chat(message)
        self.memory.put_message(user_message)
        
        # Create assistant message
        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=str(response)
        )

        self.memory.put_message(assistant_message)
        
        return str(response)
    
    def check_followups(self) -> List[Dict]:
        """Check for any pending follow-ups"""
        return self.memory.get_pending_followups()
    
    def generate_followup_message(self, followup: Dict, followup_type: str = None) -> tuple[str, str]:
        """Generate appropriate follow-up message based on context"""
        context = self.memory.get()  # Get chat history
        
        # If followup_type is provided, use it; otherwise, use the type from the followup
        if followup_type is None:
            followup_type = followup['type']

        
        followup_prompt = f"""
        Generate 简短的中文短信 for a follow-up.
        Previous conversation: {context}
        Follow-up type: {followup_type}
        Follow-up context: {followup['context']}
        
        The message should taken into account the previous conversation and the follow-up context and be:
        1. Brief and to the point
        2. Friendly and polite
        3. Clear about why we're following up
        """
        
        response = self.llm.complete(followup_prompt)
        return str(response), followup_type

# Usage example
if __name__ == "__main__":
    api_key = os.environ["OPENAI_API_KEY"]
    agent = FollowUpAgent(api_key)
    
    # Example conversation
    response = agent.process_message("我凌晨1点后有空，到时候再聊吧", "user1")
    # print(f"Agent: {response}")
    
    # Check for follow-ups (would typically be run by a scheduler)
    followup = agent.check_followups()[-1]
    followup_msg, followup_type = agent.generate_followup_message(followup)
    print(f"Follow-up({followup_type}): {followup_msg}")

