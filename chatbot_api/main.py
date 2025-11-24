# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv
# import os
# from openai import OpenAI

# load_dotenv()

# app = FastAPI()

# # ====== CORS (mütləq lazımdır) ======
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "https://elvin-codebase.onrender.com",
#         "https://elvin-babanli.com",
#         "https://www.elvin-babanli.com",
#     ],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ====== OpenAI setup ======
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# class ChatRequest(BaseModel):
#     message: str
#     history: list = []

# @app.post("/chat")
# async def chat_endpoint(req: ChatRequest):
#     try:
#         messages = [{"role": h["role"], "content": h["content"]} for h in req.history]
#         messages.append({"role": "user", "content": req.message})

#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=messages,
#             max_tokens=200
#         )

#         reply = response.choices[0].message.content
#         return {"reply": reply}

#     except Exception as e:
#         print("Chat error:", e)
#         return {"reply": "Sorry, I couldn’t reply right now."}
