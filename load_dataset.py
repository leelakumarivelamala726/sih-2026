from datasets import load_dataset

dataset = load_dataset(
    "ai4bharat/MILU",
    data_dir="Telugu",
    split="test"
)

print(dataset)
print(dataset[0])