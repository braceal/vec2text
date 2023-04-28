from typing import Dict, Tuple, Union

import torch

from models import JointEmbeddingTextEncoder
from run_args import TrainingArguments

from .base import BaseTrainer
from .inversion import InversionTrainer

from models.model_utils import freeze_params


class CorrectorTrainer(BaseTrainer):
    def __init__(
        self,
        model: JointEmbeddingTextEncoder,
        inversion_trainer: InversionTrainer,
        args: TrainingArguments,
    ):
        # Freeze other model params
        freeze_params(inversion_trainer.model)
        # We're training this corrector model to correct outputs from
        # a model trained & loaded via the inversion trainer.
        self.inversion_trainer = inversion_trainer
        self.inversion_trainer.model.use_frozen_embeddings_as_input = True
        super().__init__(
            model=model,
            args=args,
            train_dataset=self.inversion_trainer.train_dataset,
            eval_dataset=self.inversion_trainer.eval_dataset,
            data_collator=self.inversion_trainer.data_collator,
        )
        self.tokenizer = self.inversion_trainer.model.tokenizer
        self.embedder_tokenizer = self.inversion_trainer.model.embedder_tokenizer
        self.call_embedding_model = self.inversion_trainer.model.call_embedding_model
        # Need to train with same device as the inversion model to avoid weird errors.
        
        assert self.args.fp16 == self.inversion_trainer.args.fp16
        assert self.args.bf16 == self.inversion_trainer.args.bf16

    def compute_loss(
        self,
        model: JointEmbeddingTextEncoder,
        inputs: Dict[str, torch.Tensor],
        return_outputs: bool = False,
    ) -> Union[Tuple[torch.Tensor, Dict[str, torch.Tensor]], torch.Tensor]:
        """Computes contrastive loss using model generations and real text."""
        batch_size, seq_length = inputs["input_ids"].shape

        with torch.no_grad():
            frozen_embeddings = self.inversion_trainer.model.call_embedding_model(
                input_ids=inputs["embedder_input_ids"],
                attention_mask=inputs["embedder_attention_mask"],
            )
        new_embeddings = self.model(
            embedding=frozen_embeddings,
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
        )

        # TODO: support passing embedder_input_ids/attention_mask as None.
        fake_embedder_input_ids = torch.ones([1], device=self.args.device)
        fake_embedder_attention_mask = torch.ones([1], device=self.args.device)
        return inversion_trainer.model(
            embedder_input_ids=fake_embedder_input_ids,
            embedder_attention_mask=fake_embedder_attention_msak,
            labels=inputs["labels"],
            frozen_embeddings=new_embeddings,
        )
