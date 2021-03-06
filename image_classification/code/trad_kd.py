import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.functional")
from comet_ml import Experiment
from fastai.vision import *
import torch
import argparse
from torchsummary import summary
from core import SaveFeatures
from utils import _get_accuracy
from models.custom_resnet import *
torch.cuda.set_device(0)

parser = argparse.ArgumentParser(description = 'Traditional KD of ResNet type model')
parser.add_argument('-m', choices = ['resnet10', 'resnet14', 'resnet18', 'resnet20', 'resnet26'], help = 'Give the model name from the choices')
parser.add_argument('-d', choices = ['imagenette', 'imagewoof', 'cifar10'], help = 'Give the dataset name from the choices')
parser.add_argument('-s', type = int, help = 'Give random seed')
parser.add_argument('-e', type = int, help = 'Give number of epochs for training')
args = parser.parse_args()

val = 'val'
sz = 224
stats = imagenet_stats
num_epochs = args.e
batch_size = 64
# dataset = 'imagenette'
# model_name = 'resnet26'
dataset = args.d
model_name = args.m

if dataset == 'imagenette' : 
    path = untar_data(URLs.IMAGENETTE)
elif dataset == 'cifar10' : 
    path = untar_data(URLs.CIFAR)
elif dataset == 'imagewoof' : 
    path = untar_data(URLs.IMAGEWOOF)

torch.manual_seed(args.s)
torch.cuda.manual_seed(args.s)

val = 'val'
sz = 224
stats = imagenet_stats

# stage should be in 0 to 5 (5 for classifier stage)
hyper_params = {
    "dataset": dataset,
    "model": model_name,
    "repeated": args.s,
    "num_classes": 10,
    "batch_size": batch_size,
    "num_epochs": num_epochs,
    "learning_rate": 1e-4
}

load_name = str(hyper_params['dataset'])
tfms = get_transforms(do_flip=False)
if hyper_params['dataset'] == 'cifar10' : 
    val = 'test'
    sz = 32
    stats = cifar_stats
    load_name = str(hyper_params['dataset'])[ : -2]

data = ImageDataBunch.from_folder(path, train = 'train', valid = val, bs = hyper_params["batch_size"], size = sz, ds_tfms = tfms).normalize(stats)

learn = cnn_learner(data, models.resnet34, metrics = accuracy)
learn = learn.load('resnet34_' + load_name + '_bs64')
learn.freeze()

if hyper_params['model'] == 'resnet10' :
    net = resnet10(pretrained = False, progress = False)
elif hyper_params['model'] == 'resnet14' : 
    net = resnet14(pretrained = False, progress = False)
elif hyper_params['model'] == 'resnet18' :
    net = resnet18(pretrained = False, progress = False)
elif hyper_params['model'] == 'resnet20' :
    net = resnet20(pretrained = False, progress = False)
elif hyper_params['model'] == 'resnet26' :
    net = resnet26(pretrained = False, progress = False)

if torch.cuda.is_available() : 
    net = net.cuda()

# saving outputs of all Basic Blocks
mdl = learn.model
# for all 5 feature maps
sf = [SaveFeatures(m) for m in [mdl[0][5]]]
sf2 = [SaveFeatures(m) for m in [net.layer2]]
num_fm = 1

for stage in range(1) :
    val = 'val'
    sz = 224
    stats = imagenet_stats

    # stage should be in 0 to 5 (5 for classifier stage)
    hyper_params['stage'] = stage
    
    net.cpu()
    # no need to load model for 0th stage training
    # if hyper_params['stage'] == 0 : 
    #     filename = '../saved_models/' + str(hyper_params['dataset']) + '/' + str(hyper_params['model']) + '_stage' + str(hyper_params['stage']) + '/model' + str(hyper_params['repeated']) + '.pt'
    # # separate if conditions for stage 1 and others because of irregular naming convention
    # # in the student model.
    # elif hyper_params['stage'] == 1 : 
    #     filename = '../saved_models/' + str(hyper_params['dataset']) + '/' + str(hyper_params['model']) + '_stage0/model' + str(hyper_params['repeated']) + '.pt'
    #     net.load_state_dict(torch.load(filename, map_location = 'cpu'))
    # else : 
    #     filename = '../saved_models/' + str(hyper_params['dataset']) + '/' + str(hyper_params['model']) + '_stage' + str(hyper_params['stage']) + '/model' + str(hyper_params['repeated']) + '.pt'
    #     net.load_state_dict(torch.load(filename, map_location = 'cpu'))
    
    if torch.cuda.is_available() : 
        net = net.cuda()

    # for name, param in net.named_parameters() : 
    #     param.requires_grad = False
    #     if name[5] == str(hyper_params['stage']) and hyper_params['stage'] != 0 :
    #         param.requires_grad = True
    #     elif (name[0] == 'b' or name[0] == 'c') and hyper_params['stage'] == 0 : 
    #         param.requires_grad = True

    for name, param in net.named_parameters() : 
        param.requires_grad = False
        if (name[0] == 'b' or name[0] == 'c' or name[5] == str(0) or name[5] == str(1) or name[5] == str(2)) : 
            param.requires_grad = True

    project_name = 'trad-kd-new-' + hyper_params['model'] + '-' + hyper_params['dataset']
    experiment = Experiment(api_key="1jNZ1sunRoAoI2TyremCNnYLO", project_name = project_name, workspace="akshaykvnit")
    experiment.log_parameters(hyper_params)

    filename = '../saved_models/' + str(hyper_params['dataset']) + '/trad_kd/' + str(hyper_params['model']) + '_stage' + str(hyper_params['stage']) + '/model' + str(hyper_params['repeated']) + '.pt'

    optimizer = torch.optim.Adam(net.parameters(), lr = hyper_params["learning_rate"])
    total_step = len(data.train_ds) // hyper_params["batch_size"]
    train_loss_list = list()
    val_loss_list = list()
    min_val = 100

    for epoch in range(hyper_params["num_epochs"]):
        trn = []
        net.train()
        for i, (images, labels) in enumerate(data.train_dl) :
            if torch.cuda.is_available():
                images = torch.autograd.Variable(images).cuda().float()
                labels = torch.autograd.Variable(labels).cuda()
            else : 
                images = torch.autograd.Variable(images).float()
                labels = torch.autograd.Variable(labels)

            y_pred = net(images)
            y_pred2 = mdl(images)

            loss = F.mse_loss(sf2[hyper_params["stage"]].features, sf[hyper_params["stage"]].features)
            trn.append(loss.item())

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # if i % 50 == 49 :
                # print('epoch = ', epoch + 1, ' step = ', i + 1, ' of total steps ', total_step, ' loss = ', round(loss.item(), 6))

        train_loss = (sum(trn) / len(trn))
        train_loss_list.append(train_loss)

        net.eval()
        val = []
        with torch.no_grad() :
            for i, (images, labels) in enumerate(data.valid_dl) :
                if torch.cuda.is_available():
                    images = torch.autograd.Variable(images).cuda().float()
                    labels = torch.autograd.Variable(labels).cuda()
                else : 
                    images = torch.autograd.Variable(images).float()
                    labels = torch.autograd.Variable(labels)

                # Forward pass
                y_pred = net(images)
                y_pred2 = mdl(images)
                loss = F.mse_loss(sf[hyper_params["stage"]].features, sf2[hyper_params["stage"]].features)
                val.append(loss.item())

        val_loss = sum(val) / len(val)
        val_loss_list.append(val_loss)
        
        if (epoch + 1) % 5 == 0 : 
            print('repetition : ', hyper_params["repeated"], ' | stage : ', hyper_params["stage"])
            print('epoch : ', epoch + 1, ' / ', hyper_params["num_epochs"], ' | TL : ', round(train_loss, 6), ' | VL : ', round(val_loss, 6))
        
        experiment.log_metric("train_loss", train_loss)
        experiment.log_metric("val_loss", val_loss)
        
        if val_loss < min_val :
            # print('saving model')
            min_val = val_loss
            torch.save(net.state_dict(), filename)

hyper_params['stage'] = 1

net.cpu()
filename = '../saved_models/' + str(hyper_params['dataset']) + '/trad_kd/' + str(hyper_params['model']) + '_stage0/model' + str(hyper_params['repeated']) + '.pt'
net.load_state_dict(torch.load(filename, map_location = 'cpu'))

if torch.cuda.is_available() : 
    net = net.cuda()

# for name, param in net.named_parameters() : 
#     param.requires_grad = False
#     if name[0] == 'f' :
#         param.requires_grad = True

for name, param in net.named_parameters() : 
    param.requires_grad = False
    if not (name[0] == 'b' or name[0] == 'c' or name[5] == str(0) or name[5] == str(1) or name[5] == str(2)) : 
        param.requires_grad = True

project_name = 'trad-kd-new-' + hyper_params['model'] + '-' + hyper_params['dataset']
experiment = Experiment(api_key="1jNZ1sunRoAoI2TyremCNnYLO", project_name = project_name, workspace="akshaykvnit")
experiment.log_parameters(hyper_params)
optimizer = torch.optim.Adam(net.parameters(), lr = hyper_params["learning_rate"])
total_step = len(data.train_ds) // hyper_params["batch_size"]
train_loss_list = list()
val_loss_list = list()
min_val = 0
savename = '../saved_models/' + str(hyper_params['dataset']) + '/trad_kd/' + hyper_params['model'] + '_classifier/model' + str(hyper_params['repeated']) + '.pt'
for epoch in range(hyper_params["num_epochs"]):
    trn = []
    net.train()
    for i, (images, labels) in enumerate(data.train_dl) :
        if torch.cuda.is_available():
            images = torch.autograd.Variable(images).cuda().float()
            labels = torch.autograd.Variable(labels).cuda()
        else : 
            images = torch.autograd.Variable(images).float()
            labels = torch.autograd.Variable(labels)

        y_pred = net(images)

        loss = F.cross_entropy(y_pred, labels)
        trn.append(loss.item())

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # if i % 50 == 49 :
            # print('epoch = ', epoch, ' step = ', i + 1, ' of total steps ', total_step, ' loss = ', loss.item())

    train_loss = (sum(trn) / len(trn))
    train_loss_list.append(train_loss)

    net.eval()
    val = []
    with torch.no_grad() :
        for i, (images, labels) in enumerate(data.valid_dl) :
            if torch.cuda.is_available():
                images = torch.autograd.Variable(images).cuda().float()
                labels = torch.autograd.Variable(labels).cuda()
            else : 
                images = torch.autograd.Variable(images).float()
                labels = torch.autograd.Variable(labels)

            # Forward pass
            y_pred = net(images)

            loss = F.cross_entropy(y_pred, labels)
            val.append(loss.item())

    val_loss = sum(val) / len(val)
    val_loss_list.append(val_loss)
    val_acc = _get_accuracy(data.valid_dl, net)
    experiment.log_metric("train_loss", train_loss)
    experiment.log_metric("val_loss", val_loss)
    experiment.log_metric("val_acc", val_acc * 100)

    print('epoch : ', epoch + 1, ' / ', hyper_params["num_epochs"], ' | TL : ', round(train_loss, 6), ' | VL : ', round(val_loss, 6), ' | VA : ', round(val_acc * 100, 6))

    if (val_acc * 100) > min_val :
        print('saving model')
        min_val = val_acc * 100
        torch.save(net.state_dict(), savename)
