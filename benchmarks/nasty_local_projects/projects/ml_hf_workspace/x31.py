import pandas as pd
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_NAME = "demo/competition-model"
TOKEN = "hf_demo_token"
PROMPTS_PATH = "prompts.csv"
SUBMISSION_PATH = "submission.csv"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_auth_token=TOKEN)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, use_auth_token=TOKEN)


def generate_response(prompt):
    encoded = tokenizer(prompt, return_tensors="pt")
    generated = model.generate(**encoded)
    return tokenizer.decode(generated[0], skip_special_tokens=True)


def postprocess(response):
    return response.strip().replace("\n", " ")


def build_submission():
    rows = pd.read_csv(PROMPTS_PATH)
    rows["answer"] = [postprocess(generate_response(prompt)) for prompt in rows["prompt"]]
    rows.to_csv(SUBMISSION_PATH, index=False)
    return SUBMISSION_PATH


def evaluate(query, answer):
    response = pipe(query, answer)
    return output[0]["score"]
