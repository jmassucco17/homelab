# Large Language Model

The server runs a Mistral 7B LLM, currently for experimental purposes.

Basic test:

```sh
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Write a Python function to reverse a string.",
  "stream": true
}'
```
