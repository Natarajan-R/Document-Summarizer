# -*- coding: utf-8 -*-
"""PDF-Summarizer.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1RuYWkKwPkICvkUL2dsGAq_kwVKlSnIK1
"""

#!pip install torch
!pip install transformers tqdm llama_index
!pip install PyMuPDF

import logging
import fitz  # PyMuPDF
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from tqdm.notebook import tqdm
from llama_index.core import Document
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.core.schema import Node
from llama_index.core import SimpleDirectoryReader
import os
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Example usage
pdf_path = '/content/Our-PDF-Document.pdf'  # Update this to your PDF file path
output_path = 'Our-PDF-Document-summary.txt'  # Update this to your desired output file path

# Function to extract text from a PDF, skipping the first `skip_pages` pages
def extract_text_from_pdf(pdf_path, skip_pages=3):
    pdf_document = fitz.open(pdf_path)
    text = ""
    for page_num in range(skip_pages, len(pdf_document)):
        page = pdf_document.load_page(page_num)
        text += page.get_text()
    return text

# Function to remove common unnecessary phrases (optional preprocessing)
def remove_unnecessary_phrases(text):
    unnecessary_phrases = [
      "unwanted text"
    ]
    for phrase in unnecessary_phrases:
        text = text.replace(phrase, "")
    return text

# Function to preprocess text
def preprocess_text(text):
    # Remove legal phrases (optional)
    text = remove_unnecessary_phrases(text)
    # Additional preprocessing can be added here if necessary
    return text

# Function to save summary to a file
def save_summary(summary, output_path):
    with open(output_path, 'w') as file:
        file.write(summary)

def recursive_summarization(document, tokenizer, model, generate_kwargs, chunk_size, summary_kind):
    """
    Recursively summarize a text using an LLM and NodeParser with TokenTextSplitter.

    :param document: Document object with text to summarize.
    :param tokenizer: Tokenizer of the LLM model.
    :param model: LLM model.
    :param generate_kwargs: Arguments for the model's text generation.
    :param chunk_size: Maximum token size per chunk.
    :return: Final summary of the document.
    """
    def recursive_summarization_helper(nodes):
        input_ids = []
        for node in nodes:
            input_ids.extend(node.input_ids)

        summarized_texts = []
        prompt = f"""### System:
You are an expert agent in information extraction and summarization.
### User:
Read the following context document:
---------------
{document.text}
---------------

Your tasks are as follows:
1.- Write an extensive, fluid, and continuous paragraph summarizing the most important aspects of the information you have read.
2.- You can only synthesize your response using exclusively the information from the context document.
### Assistant:
According to the context information, the summary in English is: """

        inputs = tokenizer(prompt, return_tensors='pt').to("cuda")
        tokens = model.generate(**inputs, **generate_kwargs)
        # Debugging: Print input tensor shapes
        print(f"Input tensors: {inputs}")

        # Decode the response
        completion_tokens = tokens[0][inputs["input_ids"].size(1):]
        response_text = tokenizer.decode(completion_tokens, skip_special_tokens=True)
        summarized_texts.append(response_text)

        if len(nodes) == 1:
            return summarized_texts[0]
        else:
            combined_text = ' '.join(summarized_texts).strip().strip('\n')
            new_nodes = node_parser.get_nodes_from_documents([Document(text=combined_text)])
            return recursive_summarization_helper(new_nodes)

    node_parser = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
    initial_nodes = node_parser.get_nodes_from_documents([document])
    return recursive_summarization_helper(initial_nodes)

# Main function to process the PDF and generate a comprehensive summary
def summarize_pdf(pdf_path, output_path):
    print("Summarize PDF function starts here...")

    # Check if GPU is available and load model accordingly
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    model_name = "facebook/bart-large-cnn"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model = model.to(device)  # Load the model onto the GPU

    # Extract text from the PDF, skipping the first 3 pages
    logger.info("Extracting text from PDF")
    pdf_text = extract_text_from_pdf(pdf_path, skip_pages=3)

    # Preprocess the text
    logger.info("Preprocessing text")
    preprocessed_text = preprocess_text(pdf_text)

    # Define the maximum number of tokens for each chunk
    max_tokens = 1024

    # Chunk the text
    text_chunks = chunk_text(preprocessed_text, max_tokens, tokenizer)

    # Summarize each chunk
    summaries = []
    for chunk in tqdm(text_chunks, desc="Summarizing chunks"):
        inputs = tokenizer(chunk, return_tensors='pt', max_length=max_tokens, truncation=True).to(device)
        summary_ids = model.generate(inputs['input_ids'], max_length=max_tokens, min_length=100, length_penalty=2.0, num_beams=4, early_stopping=True)
        summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        summaries.append(summary)

    # Combine all summaries into a final summary
    final_summary = " ".join(summaries)

    # Save the final summary to a file
    logger.info("Saving final summary")
    save_summary(final_summary, output_path)

# Function to chunk text into manageable pieces
def chunk_text(text, max_tokens, tokenizer):
    tokens = tokenizer.encode(text)
    chunks = [tokens[i:i + max_tokens] for i in range(0, len(tokens), max_tokens)]
    return [tokenizer.decode(chunk) for chunk in chunks]

summarize_pdf(pdf_path, output_path)