curl https://router.huggingface.co/v1/chat/completions \
    -H "Authorization: Bearer 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" \
    -H 'Content-Type: application/json' \
    -d '{
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this image in one sentence."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg"
                        }
                    }
                ]
            }
        ],
        "model": "Qwen/Qwen2.5-VL-7B-Instruct:hyperbolic",
        "stream": false
    }'