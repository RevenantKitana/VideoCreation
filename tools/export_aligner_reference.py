import torch, sys
sys.argv=[sys.argv[0],"x"]; import align
m=align.model; x=torch.randn(1,16000*4)
class W(torch.nn.Module):
    def __init__(s,m): super().__init__(); s.m=m
    def forward(s,x): return torch.log_softmax(s.m(x).logits,-1)
torch.onnx.export(W(m),(x,),"vi_ctc.onnx",input_names=["audio"],output_names=["logprobs"],
  dynamic_axes={"audio":{1:"n"},"logprobs":{1:"t"}},opset_version=17,dynamo=False)
