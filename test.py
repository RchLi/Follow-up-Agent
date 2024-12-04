import os
from datetime import datetime, timedelta
from unittest.mock import patch
from freezegun import freeze_time
from FollowUpAgent import FollowUpAgent
from llama_index.core.llms import ChatMessage, MessageRole

def test_class_followups():
    """Test short-term follow-ups for class schedule:
    - Reminder at 5:00 PM for class login
    - Reminder at 10:00 PM for class preparation
    - Follow-up after class for feedback
    """
    api_key = os.environ["OPENAI_API_KEY"]
    
    # Set initial time to 2:00 PM
    initial_time = datetime(2024, 12, 5, 14, 0)
    
    with freeze_time(initial_time) as frozen_time:
        agent = FollowUpAgent(api_key)
        
        # Process conversation messages
        conversations = [
            (datetime(2024, 12, 5, 14, 0), "我们有小班试听课，下午有兴趣来参加试听吗？", 'bot'),
            (datetime(2024, 12, 5, 14, 0), "嗷嗷；那下午看看吧", 'user'),
            (datetime(2024, 12, 5, 14, 0), "好；宝，今天有时间来参加试听吗？", 'bot'),
            (datetime(2024, 12, 5, 14, 0), "三点多才有空了", 'user'),
            (datetime(2024, 12, 5, 14, 5), "下午五点呢", 'bot'),
            (datetime(2024, 12, 5, 14, 5), "应该可以", 'user'),
            (datetime(2024, 12, 5, 14, 5), '好那就这个时间了哈', 'bot'),
            (datetime(2024, 12, 5, 14, 10), "好的，你们几点下课呢?", 'user'),
            (datetime(2024, 12, 5, 14, 10), "晚上十点呢宝", 'bot'),
            (datetime(2024, 12, 5, 14, 15), "嗯嗯", 'user'),
            (datetime(2024, 12, 5, 15, 30), "还好的，就简单讲了一下", 'user'),
            (datetime(2024, 12, 5, 16, 0), "我回去整理下，等明天回你", 'user'),
            (datetime(2024, 12, 5, 16, 30), "在外面办事呢，在家学习效果好很多", 'user'),
            (datetime(2024, 12, 5, 17, 0), '', 'bot'),
            (datetime(2024, 12, 5, 22, 0), '', 'bot'),
            (datetime(2024, 12, 5, 22, 20), '还好吧，就简单讲了一下,我回老家了开车堵车,等明天回你', 'user'),
            (datetime(2024, 12, 6, 20, 0), '', 'bot'),
        ]
        
        # Process each conversation message
        for time, msg, role in conversations:
            frozen_time.move_to(time)
            # print(f"\nCurrent time: {datetime.now()}")
            # print(f"User: {user_msg}")
            if role == 'user':
                response = agent.process_message(msg, "user1")
            else:
                chat_msg = ChatMessage(role=MessageRole.ASSISTANT, content=msg)
                agent.memory.put(chat_msg)
                agent.memory.put_message(chat_msg)
            
            # Check for follow-ups at key times
            if time.hour == 17 and time.minute == 0:
                print("\nExpected follow-up at 5:00 PM:")
                print("要准备上课了哈")
                followups = agent.check_followups()
                followup = followups[-1]
                followup_msg, followup_type = agent.generate_followup_message(followup)
                print(f"Actual follow-up({followup_type}): {followup_msg}")
            
            # After class follow-up
            elif time.hour == 22 and time.minute == 0:
                print("\nExpected follow-up at 10:00 PM:")
                print("宝子，下课了，感觉有收获吗？")
                followups = agent.check_followups()
                followup = followups[-1]
                followup_msg, followup_type = agent.generate_followup_message(followup)
                print(f"Actual follow-up({followup_type}): {followup_msg}")

            # Next day follow-up
            elif time.hour == 20 and time.minute == 0:
                print("\nExpected follow-up at 8:00 PM:")
                print("宝子，今天有空了吗？")
                followups = agent.check_followups()
                followup = followups[-1]
                followup_msg, followup_type = agent.generate_followup_message(followup)
                print(f"Actual follow-up({followup_type}): {followup_msg}")
            
            
if __name__ == "__main__":
    print("Testing class schedule follow-ups:")
    test_class_followups()
