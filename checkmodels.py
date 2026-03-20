import google.generativeai as genai

genai.configure(api_key="AIzaSyA2clAmn6oMBLj41wS5-0dDFeABVZ2YFI8")

for m in genai.list_models():
    print(m.name)
