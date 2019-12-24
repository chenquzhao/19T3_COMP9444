import numpy as np
import torch
import torch.nn as tnn
import torch.nn.functional as F
import torch.optim as topti
from torchtext import data
from torchtext.vocab import GloVe
from imdb_dataloader import IMDB


# Class for creating the neural network.
class Network(tnn.Module):
    def __init__(self):
        super(Network, self).__init__()

        self.LSTM = torch.nn.GRU(input_size=50, hidden_size=100, num_layers=3, batch_first=True, bidirectional=True)
        self.ln1 = torch.nn.Linear(in_features=100, out_features=64)
        self.relu = torch.nn.ReLU()
        self.ln2 = torch.nn.Linear(in_features=64, out_features=1)
        self.ln3 = torch.nn.Linear(in_features=6, out_features=1)
        self.drop = torch.nn.Dropout(p=0.5)

    def forward(self, input, length):
        """
        DO NOT MODIFY FUNCTION SIGNATURE
        Create the forward pass through the network.
        """
        output, hn = self.LSTM(input)
        x = self.drop(hn)
        x = self.ln1(x)
        x = self.ln2(self.relu(x))
        x = x.permute(2, 1, 0)
        x = x.view(x.shape[1], -1)
        x = self.ln3(x)
        x = x.squeeze()
        return x


class PreProcessing():
    def pre(x):
        """Called after tokenization"""
        # bedeleted = []
        # stop_word = ['the', 'a', 'and', 'of', 'to', 'is', 'in', 'i', 'this', 'that']
        # char = ['!', ',' ,'.' ,'?' ,'-s' ,'-ly' ,'</s> ', 's']
        # for i in range(len(x)):
        #     if x[i] in stop_word or x[i] in char:
        #         bedeleted.append(i)
            # elif (('!' in x[i]) or ('*' in x[i]) or ('>' in x[i]) or ('<' in x[i]) or ('(' in x[i]) or (')' in x[i]) or ('-' in x[i]) or ('\"' in x[i])):
            #     bedeleted.append(i)
 
        # x = np.delete(x, bedeleted)
        return x

    def post(batch, vocab):
        """Called after numericalization but prior to vectorization"""
        return batch

    text_field = data.Field(lower=True, include_lengths=True, batch_first=True, preprocessing=pre, postprocessing=post)


def lossFunc():
    """
    Define a loss function appropriate for the above networks that will
    add a sigmoid to the output and calculate the binary cross-entropy.
    """
    return torch.nn.BCEWithLogitsLoss()

def main():
    # Use a GPU if available, as it should be faster.
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print("Using device: " + str(device))

    # Load the training dataset, and create a data loader to generate a batch.
    textField = PreProcessing.text_field
    labelField = data.Field(sequential=False)

    train, dev = IMDB.splits(textField, labelField, train="train", validation="dev")

    textField.build_vocab(train, dev, vectors=GloVe(name="6B", dim=50))
    labelField.build_vocab(train, dev)

    trainLoader, testLoader = data.BucketIterator.splits((train, dev), shuffle=True, batch_size=64,
                                                         sort_key=lambda x: len(x.text), sort_within_batch=True)

    net = Network().to(device)
    criterion =lossFunc()
    optimiser = topti.Adam(net.parameters(), lr=0.001)  # Minimise the loss using the Adam algorithm.

    for epoch in range(11):
        running_loss = 0

        for i, batch in enumerate(trainLoader):
            # Get a batch and potentially send it to GPU memory.
            inputs, length, labels = textField.vocab.vectors[batch.text[0]].to(device), batch.text[1].to(
                device), batch.label.type(torch.FloatTensor).to(device)

            labels -= 1

            # PyTorch calculates gradients by accumulating contributions to them (useful for
            # RNNs).  Hence we must manually set them to zero before calculating them.
            optimiser.zero_grad()

            # Forward pass through the network.
            output = net(inputs, length)

            loss = criterion(output, labels)

            # Calculate gradients.
            loss.backward()

            # Minimise the loss according to the gradient.
            optimiser.step()

            running_loss += loss.item()

            if i % 32 == 31:
                print("Epoch: %2d, Batch: %4d, Loss: %.3f" % (epoch + 1, i + 1, running_loss / 32))
                running_loss = 0

    num_correct = 0

    # Save mode
    torch.save(net.state_dict(), "./model.pth")
    print("Saved model")

    net.eval()
    # Evaluate network on the test dataset.  We aren't calculating gradients, so disable autograd to speed up
    # computations and reduce memory usage.
    with torch.no_grad():
        for batch in testLoader:
            # Get a batch and potentially send it to GPU memory.
            inputs, length, labels = textField.vocab.vectors[batch.text[0]].to(device), batch.text[1].to(
                device), batch.label.type(torch.FloatTensor).to(device)

            labels -= 1

            # Get predictions
            outputs = torch.sigmoid(net(inputs, length))
            predicted = torch.round(outputs)

            num_correct += torch.sum(labels == predicted).item()

    accuracy = 100 * num_correct / len(dev)

    print(f"Classification accuracy: {accuracy}")

if __name__ == '__main__':
    main()