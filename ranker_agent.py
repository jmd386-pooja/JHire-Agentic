import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

def rank_candidates_with_llm_combined(excel_path, jd_data_science, jd_data_engineer, jd_full_stack, threshold=0.4):
    try:
        df = pd.read_excel(excel_path)
    except FileNotFoundError:
        print(f"Error: The file '{excel_path}' was not found.")
        return


    # Normalize categories for matching
    # df['Category'] = df['Category'].astype(str).str.strip().str.lower()

    print("Loading Sentence-Transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Combine resume fields
    df['combined_text'] = (
        df.get('Technical Skills', '').fillna('') + ' ' +
        df.get('Work Experience', '').fillna('') + ' ' +
        df.get('Certifications (if any)', '').fillna('') + ' ' +
        df.get('Degrees', '').fillna('')
    )

    def filter_category(df, keyword):
        return df[df['Category'].str.lower().str.contains(keyword.lower(), na=False)]

    

    print("Ranking Data Science candidates...")
    ds_df = process_category_with_llm(
        filter_category(df, 'data science'),
        jd_data_science,
        model,
        threshold,
        category_name='Data Science'
    )

    print("Ranking Data Engineer candidates...")
    de_df = process_category_with_llm(
        filter_category(df, 'data engineer'),
        jd_data_engineer,
        model,
        threshold,
        category_name='Data Engineer'
    )

    print("Ranking Full Stack candidates...")
    fs_df = process_category_with_llm(
        filter_category(df, 'full stack'),
        jd_full_stack,
        model,
        threshold,
        category_name='Full Stack'
    )



    # Align them into a single table
    max_len = max(len(ds_df), len(de_df), len(fs_df))
    combined_df = pd.DataFrame({
        "Data Science": ds_df['Full Name'].tolist() + [None]*(max_len - len(ds_df)),
        "DS Score": ds_df['score'].tolist() + [None]*(max_len - len(ds_df)),
        "Data Engineer": de_df['Full Name'].tolist() + [None]*(max_len - len(de_df)),
        "DE Score": de_df['score'].tolist() + [None]*(max_len - len(de_df)),
        "Full Stack": fs_df['Full Name'].tolist() + [None]*(max_len - len(fs_df)),
        "FS Score": fs_df['score'].tolist() + [None]*(max_len - len(fs_df)),
    })

    output_excel = 'llm_ranked_candidates_combined.xlsx'
    combined_df.to_excel(output_excel, index=False)
    print(f"\nRanking complete! Results saved to '{output_excel}'.")

    return combined_df


def process_category_with_llm(category_df, job_description, model, threshold, category_name):
    if category_df.empty:
        print(f"No candidates found in category '{category_name}'")
        return pd.DataFrame(columns=['Full Name', 'score'])

    jd_embedding = model.encode([job_description])
    resume_embeddings = model.encode(category_df['combined_text'].tolist())
    category_df['score'] = cosine_similarity(jd_embedding, resume_embeddings).flatten()

    # Debug: Show all scores
    print(f"\n--- All scores for {category_name} ---")
    print(category_df[['Full Name', 'score']].sort_values('score', ascending=False).head(10))

    # Filter by threshold
    ranked_df = category_df[category_df['score'] >= threshold].copy()
    if ranked_df.empty:
        print(f"No candidates met the threshold {threshold} for {category_name}, returning top 5 instead.")
        ranked_df = category_df.sort_values(by='score', ascending=False).head(5)

    return ranked_df[['Full Name', 'score']]



# --- Example Usage ---

# Define job descriptions for each category
jd_data_science = """
Looking for a data scientist with expertise in machine learning, deep learning,
and Python. Must have experience with libraries like TensorFlow, PyTorch,
and scikit-learn. Strong background in statistical modeling, data analysis,
and data visualization is required.
"""

jd_data_engineer = """
Seeking a data engineer proficient in building data pipelines using ETL/ELT
processes. Strong skills in SQL, Python, and big data technologies like
Hadoop, Spark, and Kafka are essential. Experience with cloud platforms
such as AWS, GCP, or Azure is a must.
"""

jd_full_stack = """
Hiring a full stack developer with strong command of both front-end and
back-end technologies. Proficient in JavaScript frameworks (React, Angular,
or Vue), Node.js, and Express. Experience with databases like MongoDB
or PostgreSQL, and RESTful API development is crucial.
"""

# Run the ranking function
input_excel = 'resumes.xlsx'
rank_candidates_with_llm_combined(input_excel, jd_data_science, jd_data_engineer, jd_full_stack, threshold=0.1)
