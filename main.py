import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from tqdm import tqdm
from torch.optim import Adam
from torchvision.datasets import MNIST, CIFAR10, CIFAR100
from torchvision.transforms import Compose, ToTensor, Normalize, Lambda
from torch.utils.data import DataLoader
# from torchinfo import summary
####### NOTE: ######
# For future experiments, replace this functionl; load different dataset for performance analysis

# Create dataloaders
def MNIST_loaders(train_batch_size=50000, test_batch_size=10000):

    # Define image transform: Turn image to Tensor, normalize data, and flatten the image to one two dimensions
    transform = Compose([
        ToTensor(),
        Normalize((0.1307,), (0.3081,)),
        Lambda(lambda x: torch.flatten(x))])

    # Load data from MNIST dataset (train and test data)
    # If downloaded, load from specified path
    # Otherwise, download to local storage from PyTorch
    train_loader = DataLoader(
        MNIST('./data/', train=True,
              download=True,
              transform=transform),
        batch_size=train_batch_size, shuffle=True)

    test_loader = DataLoader(
        MNIST('./data/', train=False,
              download=True,
              transform=transform),
        batch_size=test_batch_size, shuffle=False)

    return train_loader, test_loader

def CIFAR10_loaders(train_batch_size=25000, test_batch_size=10000):
    # Define image transform: Turn image to Tensor, normalize data, and flatten the image to one two dimensions
    transform = Compose([
        ToTensor(),
        Normalize((0.1307,), (0.3081,)),
        Lambda(lambda x: torch.flatten(x))])

    # Load data from CIFAR-10 dataset (train and test data)
    # If downloaded, load from specified path
    # Otherwise, download to local storage from PyTorch
    train_loader = DataLoader(
        CIFAR10('./data/', train=True,
              download=True,
              transform=transform),
        batch_size=train_batch_size, shuffle=True)

    test_loader = DataLoader(
        CIFAR10('./data/', train=False,
              download=True,
              transform=transform),
        batch_size=test_batch_size, shuffle=False)

    return train_loader, test_loader

def CIFAR100_loaders(train_batch_size=25000, test_batch_size=10000):
    # Define image transform: Turn image to Tensor, normalize data, and flatten the image to one two dimensions
    transform = Compose([
        ToTensor(),
        Normalize((0.1307,), (0.3081,)),
        Lambda(lambda x: torch.flatten(x))])

    # Load data from CIFAR-100 dataset (train and test data)
    # If downloaded, load from specified path
    # Otherwise, download to local storage from PyTorch
    train_loader = DataLoader(
        CIFAR100('./data/', train=True,
              download=True,
              transform=transform),
        batch_size=train_batch_size, shuffle=True)

    test_loader = DataLoader(
        CIFAR100('./data/', train=False,
              download=True,
              transform=transform),
        batch_size=test_batch_size, shuffle=False)

    return train_loader, test_loader


def overlay_y_on_x(x, y):
    """Replace the first 10 pixels of data [x] with one-hot-encoded label [y]
    """
    x_ = x.clone()
    x_[:, :10] *= 0.0
    x_[range(x.shape[0]), y] = x.max()
    return x_


class Net(torch.nn.Module):

    def __init__(self, dims):
        super().__init__()
        # Store the layers in a list so each can be trained individually
        self.layers = []

        # Append each new layer to the list
        for d in range(len(dims) - 1):
            self.layers += [Layer(dims[d], dims[d + 1])] # .cuda()]

    def predict(self, x):
        # This function calculates the amount of neural activity for each label
        # The prediction retured is the integer label with the highest neural activity, or the "maximum goodness"
        goodness_per_label = []
        for label in range(10): # For each possible integer label:
            h = overlay_y_on_x(x, label) # Overlay y on x as specified by Hinton
            goodness = []
            # Calculate summed goodness for given label
            for layer in self.layers:
                h = layer(h)
                goodness += [h.pow(2).mean(1)]
            goodness_per_label += [sum(goodness).unsqueeze(1)]
        goodness_per_label = torch.cat(goodness_per_label, 1)
        return goodness_per_label.argmax(1) # Return label with the max summed goodness

    def train(self, x_pos, x_neg):
        # Train each layer in sequence amounts to training the whole network
        h_pos, h_neg = x_pos, x_neg
        for i, layer in enumerate(self.layers):
            print('training layer', i, '...')
            h_pos, h_neg = layer.train(h_pos, h_neg)


class Layer(nn.Linear):
    def __init__(self, in_features, out_features,
                 bias=True, device=None, dtype=None):
        super().__init__(in_features, out_features, bias)
        # Initialize hyperparameters and reusable functions
        self.relu = torch.nn.ReLU()
        self.opt = Adam(self.parameters(), lr=0.03)
        self.threshold = 2.0
        self.num_epochs = 1000

    def forward(self, x):
        # Normalize x and pass x through the layer weights
        x_direction = x / (x.norm(2, 1, keepdim=True) + 1e-4)
        return self.relu(
            torch.mm(x_direction, self.weight.T) +
            self.bias.unsqueeze(0))

    def train(self, x_pos, x_neg):
        for i in tqdm(range(self.num_epochs)):
            # Pass positive and negative data through the layer weights; then take mean squared
            g_pos = self.forward(x_pos).pow(2).mean(1)
            g_neg = self.forward(x_neg).pow(2).mean(1)
            # The following loss pushes pos (neg) samples to
            # values larger (smaller) than the self.threshold.
            loss = torch.log(1 + torch.exp(torch.cat([
                -g_pos + self.threshold,
                g_neg - self.threshold]))).mean()
            self.opt.zero_grad()
            # this backward just compute the derivative and hence
            # is not considered backpropagation.
            loss.backward()
            self.opt.step()
        return self.forward(x_pos).detach(), self.forward(x_neg).detach()
    

# Create network for backpropogation optimization
class BPNet(nn.Module):
    def __init__(self, dims, num_classes=10):
        super().__init__()

        self.layers = []
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax()

        for d in range(len(dims) - 1):
            self.layers += [nn.Linear(dims[d], dims[d + 1]), nn.LayerNorm(dims[d+1]), self.relu]
        self.layers += [nn.Linear(dims[-1], num_classes)]
        
        self.f = nn.Sequential(*self.layers)

    def forward(self, x):
        return self.softmax(self.f(x))


def visualize_sample(data, name='', idx=0):
    # Plot samples
    reshaped = data[idx].cpu().reshape(28, 28)
    plt.figure(figsize = (4, 4))
    plt.title(name)
    plt.imshow(reshaped, cmap="gray")
    plt.show()

# Train network with backpropogation
def train(model, device, train_loader, optimizer, loss_fn, epoch):
    model.train()
    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.to(device), target.to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = loss_fn(output, target)
        loss.backward()
        optimizer.step()
        if batch_idx % 100 == 0:
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, batch_idx * len(data), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item()))

# Test network for backpropogation; get avg. loss
def test(model, device, test_loader, loss_fn):
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            test_loss += loss_fn(output, target).item()  # sum up batch loss
            pred = output.argmax(dim=1, keepdim=True)  # get the index of the max log-probability
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)

    print('\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
        test_loss, correct, len(test_loader.dataset),
        100. * correct / len(test_loader.dataset)))

    
    
if __name__ == "__main__":

    # Train network

    torch.manual_seed(1234)

    # Load Dataset: MNSIT, CIFAR10, or CIFAR100
    train_loader, test_loader = MNIST_loaders()

    # Define network dimensions for BOTH backprop and FF.
    # Equivalent networks will be created.
    dims = [784, 500, 500]
    num_classes = 10

    # Define Networks
    ff_net = Net(dims)
    bp_net = BPNet(dims, num_classes)

    
    ###### TRAIN FF ######

    x, y = next(iter(train_loader))
    x, y = x.cuda(), y.cuda()
    x_pos = overlay_y_on_x(x, y)
    rnd = torch.randperm(x.size(0))
    x_neg = overlay_y_on_x(x, y[rnd])
    
    for data, name in zip([x, x_pos, x_neg], ['orig', 'pos', 'neg']):
        visualize_sample(data, name)
    
    # Train whole net with FF; Loop through individual layer training
    ff_net.train(x_pos, x_neg)

    print('train error:', 1.0 - ff_net.predict(x).eq(y).float().mean().item())

    x_te, y_te = next(iter(test_loader))
    x_te, y_te = x_te.cuda(), y_te.cuda()

    print('test error:', 1.0 - ff_net.predict(x_te).eq(y_te).float().mean().item())
    

    ###### TRAIN BP ######

    lr = .001
    loss_fn = nn.CrossEntropyLoss()
    opt = torch.optim.Adam(bp_net.parameters(), lr=lr)
    epochs = 100
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # High level training loop
    for epoch in range(epochs):
        train(bp_net, device, train_loader, opt, loss_fn, epoch)
        test(bp_net, device, test_loader, loss_fn)