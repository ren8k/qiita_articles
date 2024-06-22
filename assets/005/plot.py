import io
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text

# Read the CSV data
data = """
model, date, chatbot arena elo score
Claude3.5 Sonnet (???), 2024/6/20, 1290
GPT-4o,2024/5/13, 1287
GPT-3.5-Turbo-0613, 2023/6/13, 1117
Gemini-1.5-pro,2024/5/14, 1265
Claude3 Opus, 2024/3/4, 1249
Claude3 Sonnet, 2024/3/4, 1201
Claude3 Haiku,2024/3/14, 1179
Command R+,2024/4/4,1148
Mistral-Large, 2024/2/26, 1157
Mistral-8x22b, 2024/4/10, 1146
Nemotron-4-340B-Instruct, 2024/6/14, 1208
Llama3 70B, 2024/4/18,1207
Llama3 8B, 2024/4/18,1153
Qwen2-72B-Instruct, 2024/6/6, 1187
"""

# Convert the string data to a DataFrame
df = pd.read_csv(io.StringIO(data.strip()), skipinitialspace=True)

# Strip whitespace from column names
df.columns = df.columns.str.strip()

# Convert date strings to datetime objects
df["date"] = pd.to_datetime(df["date"], format="%Y/%m/%d")

# Define the models to be highlighted in red
highlight_models = [
    "Claude3.5 Sonnet (???)",
    "Claude3 Opus",
    "Claude3 Sonnet",
    "Claude3 Haiku",
    "Command R+",
    "Mistral-Large",
    "Llama3 70B",
    "Llama3 8B",
]

# Create the scatter plot
plt.figure(figsize=(16, 12))

# Add grid
plt.grid(True, linestyle="--", alpha=0.7)

texts = []
for _, row in df.iterrows():
    color = "red" if row["model"] in highlight_models else "blue"
    plt.scatter(row["date"], row["chatbot arena elo score"], c=color, s=120)
    texts.append(
        plt.text(row["date"], row["chatbot arena elo score"], row["model"], fontsize=14)
    )

# Adjust text positions to minimize overlap
adjust_text(texts, arrowprops=dict(arrowstyle="->", color="gray", lw=0.5))

plt.xlabel("Release Date", fontsize=16)
plt.ylabel("Chatbot Arena Elo Rate", fontsize=16)
# plt.title("Chatbot Arena Elo Scores by Release Date", fontsize=14)

# Rotate x-axis labels for better readability
plt.gcf().autofmt_xdate()

# Add a legend
plt.scatter([], [], c="red", label="Available Model on Bedrock", s=150)
plt.scatter([], [], c="blue", label="Closed Model", s=150)
plt.legend()

plt.tight_layout()
plt.savefig("chatbot_arena_elo_scores.png", dpi=400, bbox_inches="tight")
plt.show()
