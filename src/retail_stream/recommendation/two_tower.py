from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class TwoTower(nn.Module):
    def __init__(
        self,
        num_users: int,
        num_items: int,
        num_categories: int,
        embedding_dim: int = 64,
        hidden_dim: int = 128,
    ) -> None:
        super().__init__()
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        self.category_embedding = nn.Embedding(num_categories, embedding_dim // 2)
        self.user_mlp = nn.Sequential(
            nn.Linear(embedding_dim + 3, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, embedding_dim),
        )
        self.item_mlp = nn.Sequential(
            nn.Linear(embedding_dim + embedding_dim // 2 + 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, embedding_dim),
        )

    def encode_user(self, user_ids, user_features):
        vector = self.user_mlp(
            torch.cat((self.user_embedding(user_ids), user_features), dim=-1)
        )
        return F.normalize(vector, dim=-1)

    def encode_item(self, item_ids, category_ids, item_features):
        inputs = torch.cat(
            (
                self.item_embedding(item_ids),
                self.category_embedding(category_ids),
                item_features,
            ),
            dim=-1,
        )
        return F.normalize(self.item_mlp(inputs), dim=-1)

    def forward(
        self,
        user_ids,
        user_features,
        positive_item_ids,
        positive_category_ids,
        positive_item_features,
        negative_item_ids,
        negative_category_ids,
        negative_item_features,
    ):
        users = self.encode_user(user_ids, user_features)
        positives = self.encode_item(
            positive_item_ids, positive_category_ids, positive_item_features
        )
        negatives = self.encode_item(
            negative_item_ids, negative_category_ids, negative_item_features
        )
        return (users * positives).sum(dim=-1), (users * negatives).sum(dim=-1)
