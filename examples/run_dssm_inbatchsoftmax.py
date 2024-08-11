import pandas as pd

import sys
sys.path.append("/Users/nh/code/rec推荐/DeepMatch")

from deepctr.feature_column import SparseFeat, VarLenSparseFeat
from deepmatch.models import *
from deepmatch.utils import sampledsoftmaxloss, NegativeSampler
from preprocess import gen_data_set, gen_model_input
from sklearn.preprocessing import LabelEncoder
from tensorflow.python.keras.models import Model

if __name__ == "__main__":

    # data = pd.read_csvdata = pd.read_csv("./movielens_sample.txt")
    # data = pd.read_csv("/Users/nh/code/rec推荐/DeepMatch/examples/movielens_sample.txt")
    # data = pd.read_csv("/Users/nh/code/rec推荐/DeepMatch/examples/movielens_all.csv")
    data = pd.read_csv("/Users/nh/code/rec推荐/DeepMatch/examples/movielens_1_of_10.csv")

    sparse_features = ["movie_id", "user_id",
                       "gender", "age", "occupation", "zip", "genres"]
    SEQ_LEN = 50
    # negsample = 10
    negsample = 3

    # 1.Label Encoding for sparse features,and process sequence features with `gen_date_set` and `gen_model_input`

    feature_max_idx = {}
    for feature in sparse_features:
        lbe = LabelEncoder()
        data[feature] = lbe.fit_transform(data[feature]) + 1
        feature_max_idx[feature] = data[feature].max() + 1

    user_profile = data[["user_id", "gender", "age", "occupation", "zip"]].drop_duplicates('user_id')

    item_profile = data[["movie_id", "genres"]].drop_duplicates('movie_id')

    user_profile.set_index("user_id", inplace=True)

    user_item_list = data.groupby("user_id")['movie_id'].apply(list)

    train_set, test_set = gen_data_set(data, SEQ_LEN, negsample, test_sample_num = 1)

    train_model_input, train_label = gen_model_input(train_set, user_profile, SEQ_LEN)
    test_model_input, test_label = gen_model_input(test_set, user_profile, SEQ_LEN)

    # 2.count #unique features for each sparse field and generate feature config for sequence feature

    embedding_dim = 32

    user_feature_columns = [SparseFeat('user_id', feature_max_idx['user_id'], embedding_dim),
                            SparseFeat("gender", feature_max_idx['gender'], embedding_dim),
                            SparseFeat("age", feature_max_idx['age'], embedding_dim),
                            SparseFeat("occupation", feature_max_idx['occupation'], embedding_dim),
                            SparseFeat("zip", feature_max_idx['zip'], embedding_dim),
                            VarLenSparseFeat(SparseFeat('hist_movie_id', feature_max_idx['movie_id'], embedding_dim,
                                                        embedding_name="movie_id"), SEQ_LEN, 'mean', 'hist_len'),
                            VarLenSparseFeat(SparseFeat('hist_genres', feature_max_idx['genres'], embedding_dim,
                                                        embedding_name="genres"), SEQ_LEN, 'mean', 'hist_len'),
                            ]

    item_feature_columns = [SparseFeat('movie_id', feature_max_idx['movie_id'], embedding_dim),
                            SparseFeat('genres', feature_max_idx['genres'], embedding_dim)
                            ]

    from collections import Counter

    train_counter = Counter(train_model_input['movie_id'])
    item_count = [train_counter.get(i, 0) for i in range(item_feature_columns[0].vocabulary_size)]
    sampler_config = NegativeSampler('inbatch', num_sampled=5, item_name='movie_id', item_count=item_count)

    # 3.Define Model and train

    import tensorflow as tf

    if tf.__version__ >= '2.0.0':
        tf.compat.v1.disable_eager_execution()
    else:
        K.set_learning_phase(True)

    model = DSSM(user_feature_columns, item_feature_columns, loss_type="softmax", sampler_config=sampler_config)
    # model = FM(user_feature_columns, item_feature_columns, loss_type="softmax", sampler_config=sampler_config)

    model.compile(optimizer='adagrad', loss=sampledsoftmaxloss)

    history = model.fit(train_model_input, train_label,
                        batch_size=256, epochs=20, verbose=1, validation_split=0.0, )

    # 4. Generate user features for testing and full item features for retrieval
    test_user_model_input = test_model_input
    all_item_model_input = {"movie_id": item_profile['movie_id'].values, "genres": item_profile['genres'].values}

    user_embedding_model = Model(inputs=model.user_input, outputs=model.user_embedding)
    item_embedding_model = Model(inputs=model.item_input, outputs=model.item_embedding)

    user_embs = user_embedding_model.predict(test_user_model_input, batch_size=2 ** 12)
    item_embs = item_embedding_model.predict(all_item_model_input, batch_size=2 ** 12)

    print(user_embs.shape)
    print(item_embs.shape)

    # 5. [Optional] ANN search by faiss and evaluate the result

    test_true_label = {line[0]:[line[1]] for line in test_set}
    
    import numpy as np
    import faiss
    from tqdm import tqdm
    from deepmatch.utils import recall_N
    
    index = faiss.IndexFlatIP(embedding_dim)
    # faiss.normalize_L2(item_embs)
    index.add(item_embs)
    # faiss.normalize_L2(user_embs)
    D, I = index.search(user_embs, 50)
    s = []
    hit = 0
    for i, uid in tqdm(enumerate(test_user_model_input['user_id'])):
        try:
            pred = [item_profile['movie_id'].values[x] for x in I[i]]
            filter_item = None
            recall_score = recall_N(test_true_label[uid], pred, N=50)
            s.append(recall_score)
            if test_true_label[uid] in pred:
                hit += 1
        except:
            print(i)
    print("recall", np.mean(s))
    print("hr", hit / len(test_user_model_input['user_id']))
