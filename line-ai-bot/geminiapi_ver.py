import google.generativeai as genai

genai.configure(api_key="APIのキー値")

models = genai.list_models()
for model in models:
    print(model.name)
