import pandas as pd

data_path = '/Users/nh/data/MovieLen1M/ml-1m/'

# Define file paths
ratings_file = data_path + 'ratings.dat'
movies_file = data_path + 'movies.dat'
users_file = data_path + 'users.dat'

# Read the data
ratings = pd.read_csv(ratings_file,sep='::',engine='python', names=['user_id', 'movie_id', 'rating', 'timestamp'])

movies = pd.read_csv(movies_file,sep='::',engine='python',names=['movie_id','title','genres'])

users = pd.read_csv(users_file,sep='::',engine='python',names=['user_id', 'gender', 'age', 'occupation', 'zip'])

# Merge the data
merged_data = pd.merge(pd.merge(ratings, movies, on='movie_id'), users, on='user_id')

# Reorder columns
merged_data = merged_data[['user_id', 'movie_id', 'rating', 'timestamp', 'title', 'genres', 'gender', 'age', 'occupation', 'zip']]

# Write to CSV
merged_data.to_csv('movielens_merged.csv', index=False)

print("Data successfully written to movielens_all.csv")
