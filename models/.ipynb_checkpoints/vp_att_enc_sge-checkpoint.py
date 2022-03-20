import torch
import torch.nn as nn
import torch.nn.functional as F

from .vp_att import FeedForward
from .Sparsemax import Sparsemax

"""
该文件下包含三个类的定义与实现：
1）SCAttEnc - 核心的注意力实现（通过qkv，计算注意力权重及加权求和）
2）MultiHeadAttentionEnc - 多头注意力机制实现
3）VP_Refine_Module - 视觉特征增强层
关系：3）-调用-> 2）-调用-> 1）
"""


# --------------   XLAN   --------------
# XLAN SCAtt 模块
class SCAttEnc(nn.Module):
    def __init__(self, mid_dims, mid_dropout):
        super(SCAttEnc, self).__init__()
        self.attention_basic = nn.Sequential(
            nn.Linear(mid_dims[0], mid_dims[1]), 
            nn.ReLU(), 
            nn.Dropout(mid_dropout)
        )
        
        self.attention_last = nn.Linear(mid_dims[-2], 1)
        self.attention_last2 = nn.Linear(mid_dims[-2], mid_dims[-1])
        
    def forward(self, query, key, att_mask, value1, value2):
        # query [B, 8, 128]
        # key [B, 8, M, 128]
        # att_mask [B, M]
        # value1 [B, 8, 128]
        # value2 [B, 8, M, 128]
        
        att_map = query.unsqueeze(-2) * key  # [B, 8, M, 128]
        att_map = self.attention_basic(att_map) # [B, 8, M, 64]
        
        if att_mask is not None:
            att_mask = att_mask.unsqueeze(1)
            att_mask_ext = att_mask.unsqueeze(-1)
            att_map_pool = torch.sum(att_map * att_mask_ext, -2) / torch.sum(att_mask_ext, -2)
        else:
            att_map_pool = att_map.mean(-2)  # [B, 8, 64]
        
        # Spatial Attention
        alpha_spatial = self.attention_last(att_map)  # [B, 8, M, 1]
        alpha_spatial = alpha_spatial.squeeze(-1)     # [B, 8, M]
        if att_mask is not None:
            alpha_spatial = alpha_spatial.masked_fill(att_mask == 0, -1e9)
        alpha_spatial = F.softmax(alpha_spatial, dim=-1)
        
        if len(alpha_spatial.shape) == 4: # batch_size * head_num * seq_num * seq_num (for xtransformer)
            value2 = torch.matmul(alpha_spatial, value2)
        else:
            value2 = torch.matmul(alpha_spatial.unsqueeze(-2), value2).squeeze(-2)  # [B, 8, 128]

        # Channel Attention
        alpha_channel = self.attention_last2(att_map_pool)
        alpha_channel = torch.sigmoid(alpha_channel)  # [B, 8, 128]
        
        attn = value1 * value2 * alpha_channel
        
        return attn
    
    
class MultiHeadAttentionEnc(nn.Module):
    def __init__(self, embed_dim, att_type, att_heads, att_mid_dim, att_mid_drop, dropout):
        super(MultiHeadAttentionEnc, self).__init__()
        self.embed_dim = embed_dim
        self.num_heads = att_heads
        self.head_dim = embed_dim // self.num_heads
        self.scaling = self.head_dim ** -0.5
        output_dim = embed_dim

        # query1 用于全局特征增强的query
        sequential = []
        sequential.append(nn.Linear(embed_dim, output_dim))
        sequential.append(nn.CELU(1.3))
        sequential.append(torch.nn.GroupNorm(self.num_heads, embed_dim))
        self.in_proj_q = nn.Sequential(*sequential)

        # keys
        sequential = []
        sequential.append(nn.Linear(embed_dim, output_dim))
        sequential.append(nn.CELU(1.3))
        sequential.append(torch.nn.GroupNorm(self.num_heads, embed_dim))
        self.in_proj_k = nn.Sequential(*sequential)

        # values1 用于通道注意力的query
        sequential = []
        sequential.append(nn.Linear(embed_dim, output_dim))
        sequential.append(nn.CELU(1.3))
        sequential.append(torch.nn.GroupNorm(self.num_heads, embed_dim))
        self.in_proj_v1 = nn.Sequential(*sequential)

        # values2 作为真正的value，同时用于空间注意力和通道注意力
        sequential = []
        sequential.append(nn.Linear(embed_dim, output_dim))
        sequential.append(nn.CELU(1.3))
        sequential.append(torch.nn.GroupNorm(self.num_heads, embed_dim))
        self.in_proj_v2 = nn.Sequential(*sequential)

        self.attn_net = SCAttEnc(att_mid_dim, att_mid_drop)
        self.dropout = nn.Dropout(dropout) if dropout > 0 else None
    
    def forward(self, query, key, mask, value1, value2, precompute=False):
        """
        输入数据：
        query1: [B, 1024]
        query2: [B, M, 1024]
        key: [B, M, 1024]
        mask: [B, M]
        value1: [B, M, 1024]
        value2: [B, M, 1024]
        """
        # 输入数据全连接层
        batch_size = query.size()[0]
        q = self.in_proj_q(query)
        
        key = key.view(-1, key.size()[-1])
        k = self.in_proj_k(key)
        
        # value1 = value1.view(-1, value1.size()[-1])
        v1 = self.in_proj_v1(value1)
        
        value2 = value2.view(-1, value2.size()[-1])
        v2 = self.in_proj_v2(value2)
        
        # 输入数据维度变换，用于多头注意力
        # [B, 8, 128]
        q = q.view(batch_size, self.num_heads, self.head_dim)
        k  = k.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        v1 = v1.view(batch_size, self.num_heads, self.head_dim)
        v2 = v2.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)

        # 调用注意力机制核心操作函数
        # 将attn_map的计算置于attn_net中进行
        attn = self.attn_net(q, k, mask, v1, v2)

        # 将输出从多头维度上恢复为正确维度
        # [B, 8, 128] --> [B, 1024]
        attn = attn.view(batch_size, self.num_heads * self.head_dim)
        
        if self.dropout is not None:
            attn = self.dropout(attn)
        
        return attn

    
# 方式一：收集每一层的gv_feat，concat之后进行Linear投影
# 用于图像目标特征的增强（用于Encoder）
# 及Visual Persistence in Encoder体现（获取主要目标）
class VP_Refine_Module(nn.Module):
    def __init__(self, embed_dim, att_type, att_heads, att_mid_dim, att_mid_drop, dropout, layer_num):
        super(VP_Refine_Module, self).__init__()
        
        self.sge_layers = nn.ModuleList([])
        self.layers = nn.ModuleList([])
        self.bifeat_emb = nn.ModuleList([])
        self.layer_norms = nn.ModuleList([]) 
        for _ in range(layer_num):
            sge_layer = SpatialGroupEnhance()
            self.sge_layers.append(sge_layer)
            
            sublayer = MultiHeadAttentionEnc(
                embed_dim = embed_dim, 
                att_type = att_type, 
                att_heads = att_heads, 
                att_mid_dim = att_mid_dim, 
                att_mid_drop = att_mid_drop,
                dropout = dropout)
            self.layers.append(sublayer)
            
            self.bifeat_emb.append(nn.Sequential(
                nn.Linear(2 * embed_dim, embed_dim),
                nn.ReLU(),
                nn.Dropout(0.3)
            ))

            self.layer_norms.append(torch.nn.LayerNorm(embed_dim))

        # gv_feat 投影
        self.proj = nn.Linear(embed_dim * (layer_num + 1), embed_dim)
        self.layer_norm = torch.nn.LayerNorm(1024)

    def forward(self, gv_feat, att_feats, att_mask, p_att_feats=None):
        if gv_feat.shape[-1] == 1:  # empty gv_feat
            gv_feat = torch.sum(att_feats * att_mask.unsqueeze(-1), 1) / torch.sum(att_mask.unsqueeze(-1), 1)
        
        feat_arr = [gv_feat]
        for i, layer in enumerate(self.layers):
            # 先使用sge进行通道增强
            att_feats = self.sge_layers[i](att_feats)
            
            # q, key, mask, v1, v2
            gv_feat = layer(gv_feat, att_feats, att_mask, gv_feat, att_feats)
            att_feats_cat = torch.cat([gv_feat.unsqueeze(1).expand_as(att_feats), att_feats], dim=-1)
            
            # att_feats 残差连接
            att_feats = self.bifeat_emb[i](att_feats_cat) + att_feats
            att_feats = self.layer_norms[i](att_feats)
            feat_arr.append(gv_feat)

        gv_feat = torch.cat(feat_arr, dim=-1)
        gv_feat = self.proj(gv_feat)
        gv_feat = self.layer_norm(gv_feat)
        return gv_feat, att_feats

    
# SGE
class SpatialGroupEnhance(nn.Module):
    def __init__(self, groups = 64):
        super(SpatialGroupEnhance, self).__init__()
        self.groups   = groups
        self.avg_pool = nn.AdaptiveAvgPool1d(1)
        # Norm
        self.weight   = nn.Parameter(torch.ones(1, groups, 1))
        self.bias     = nn.Parameter(torch.zeros(1, groups, 1))
        self.sig      = nn.Sigmoid()

    def forward(self, x): # (b, m, c)
        b, m, c = x.size()
        
        # 每一组内的通道乘以该组内特征均值
        # (b, m, c) --> (b, c, m)  --> (b*g, c/g, m)
        x = x.transpose(-1, -2).contiguous()
        x = x.view(b * self.groups, -1, m) # (b*g, c/g, m)
        xn = x * self.avg_pool(x)  # (b*g, c/g, m)
        
        # 对xn进行Norm
        xn = xn.sum(dim=1, keepdim=True) # (b*g, 1, m)
        t = xn.view(b * self.groups, -1) # (b*g, m)
        # (t - t.mean()) / t.std()
        t = t - t.mean(dim=1, keepdim=True)
        std = t.std(dim=1, keepdim=True) + 1e-5
        t = t / std  # (b*g, m)
        # reshape
        t = t.view(b, self.groups, m)
        t = t * self.weight + self.bias
        t = t.view(b * self.groups, 1, m)
        
        # Fuse
        x = x * self.sig(t)
        x = x.view(b, c, m)
        return x.transpose(-1, -2).contiguous()