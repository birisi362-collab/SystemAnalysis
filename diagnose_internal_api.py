from app.llm_client import from_environment
if __name__=='__main__':print(from_environment('profiles/internal_example.json').test_connection())
