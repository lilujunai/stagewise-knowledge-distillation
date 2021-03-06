import matplotlib.pyplot as plt
from fastai.vision import *
import torch
from torchsummary import summary
torch.cuda.set_device(0)

class Flatten(nn.Module) :
    def forward(self, input):
        return input.view(input.size(0), -1)

def conv2(ni, nf) : 
    return conv_layer(ni, nf, stride = 2)

class SaveFeatures :
    def __init__(self, m) : 
        self.handle = m.register_forward_hook(self.hook_fn)
    def hook_fn(self, m, inp, outp) : 
        self.features = outp
    def remove(self) :
        self.handle.remove()
    
def _get_accuracy(dataloader, Net):
    total = 0
    correct = 0
    Net.eval()
    for i, (images, labels) in enumerate(dataloader):
        images = torch.autograd.Variable(images).float()
        labels = torch.autograd.Variable(labels).float()
        
        if torch.cuda.is_available() : 
            images = images.cuda()
            labels = labels.cuda()

        outputs = Net.forward(images)
        outputs = F.log_softmax(outputs, dim = 1)

        _, pred_ind = torch.max(outputs, 1)
        
        # converting to numpy arrays
        labels = labels.data.cpu().numpy()
        pred_ind = pred_ind.data.cpu().numpy()
        
        # get difference
        diff_ind = labels - pred_ind
        # correctly classified will be 1 and will get added
        # incorrectly classified will be 0
        correct += np.count_nonzero(diff_ind == 0)
        total += len(diff_ind)

    accuracy = correct / total
    # print(len(diff_ind))
    return accuracy

for repeated in range(0, 1) : 
    for stage in range(4) :
        torch.manual_seed(repeated)
        torch.cuda.manual_seed(repeated)

        # stage should be in 0 to 4 (4 for classifier stage)
        hyper_params = {
            "stage": stage,
            "repeated": repeated,
            "num_classes": 10,
            "batch_size": 64,
            "num_epochs": 100,
            "learning_rate": 1e-4
        }
        
        path = untar_data(URLs.IMAGENETTE)
        tfms = get_transforms(do_flip=False)
        data = ImageDataBunch.from_folder(path, train = 'train', valid = 'val', bs = hyper_params["batch_size"], size = 224, ds_tfms = tfms).normalize(imagenet_stats)
        
        learn = cnn_learner(data, models.resnet34, metrics = accuracy)
        learn = learn.load('unfreeze_imagenet_bs64')
        learn.freeze()
        # learn.summary()

        net = nn.Sequential(
            conv_layer(3, 64, ks = 7, stride = 2, padding = 3),
            nn.MaxPool2d(3, 2, padding = 1),
            conv2(64, 128),
            conv2(128, 256),
            conv2(256, 512),
            AdaptiveConcatPool2d(),
            Flatten(),
            nn.Linear(2 * 512, 256),
            nn.Linear(256, 10)
        )

        net.cpu()
        # no need to load model for 0th stage training
        if hyper_params['stage'] == 0 : 
            filename = '../saved_models/smallest_stage' + str(hyper_params['stage']) + '/model' + str(hyper_params['repeated']) + '.pt'
        # separate if conditions for stage 1 and others because of irregular naming convention
        # in the student model.
        elif hyper_params['stage'] == 1 : 
            filename = '../saved_models/smallest_stage0/model' + str(hyper_params['repeated']) + '.pt'
            net.load_state_dict(torch.load(filename, map_location = 'cpu'))
        else : 
            filename = '../saved_models/smallest_stage' + str(hyper_params['stage']) + '/model' + str(hyper_params['repeated']) + '.pt'
            net.load_state_dict(torch.load(filename, map_location = 'cpu'))
        
        if torch.cuda.is_available() : 
            net = net.cuda()

        for name, param in net.named_parameters() : 
            param.requires_grad = False
            if name[0] == str(hyper_params['stage'] + 1) and hyper_params['stage'] != 0 :
                param.requires_grad = True
            elif name[0] == str(hyper_params['stage']) and hyper_params['stage'] == 0 : 
                param.requires_grad = True

        # saving outputs of all Basic Blocks
        mdl = learn.model
        sf = [SaveFeatures(m) for m in [mdl[0][2], mdl[0][5], mdl[0][6], mdl[0][7]]]
        sf2 = [SaveFeatures(m) for m in [net[0], net[2], net[3], net[4]]]
        
        if hyper_params['stage'] == 0 : 
            filename = '../saved_models/smallest_stage' + str(hyper_params['stage']) + '/model' + str(hyper_params['repeated']) + '.pt'
        else : 
            filename = '../saved_models/smallest_stage' + str(hyper_params['stage'] + 1) + '/model' + str(hyper_params['repeated']) + '.pt'
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
        #         torch.nn.utils.clip_grad_value_(net.parameters(), 10)
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

            if val_loss < min_val :
                # print('saving model')
                min_val = val_loss
                torch.save(net.state_dict(), filename)
                
    # Classifier training
    torch.manual_seed(repeated)
    torch.cuda.manual_seed(repeated)

    # stage should be in 0 to 5 (5 for classifier stage)
    hyper_params = {
        "stage": 4,
        "repeated": repeated,
        "num_classes": 10,
        "batch_size": 64,
        "num_epochs": 100,
        "learning_rate": 1e-4
    }

    path = untar_data(URLs.IMAGENETTE)
    tfms = get_transforms(do_flip=False)
    data = ImageDataBunch.from_folder(path, train = 'train', valid = 'val', bs = hyper_params["batch_size"], size = 224, ds_tfms = tfms).normalize(imagenet_stats)
    
    class Flatten(nn.Module) :
        def forward(self, input):
            return input.view(input.size(0), -1)

    def conv2(ni, nf) : 
        return conv_layer(ni, nf, stride = 2)

    net = nn.Sequential(
        conv_layer(3, 64, ks = 7, stride = 2, padding = 3),
        nn.MaxPool2d(3, 2, padding = 1),
        conv2(64, 128),
        conv2(128, 256),
        conv2(256, 512),
        AdaptiveConcatPool2d(),
        Flatten(),
        nn.Linear(2 * 512, 256),
        nn.Linear(256, 10)
    )

    net.cpu()
    filename = '../saved_models/smallest_stage3/model' + str(repeated) + '.pt'
    net.load_state_dict(torch.load(filename, map_location = 'cpu'))

    if torch.cuda.is_available() : 
        net = net.cuda()

    for name, param in net.named_parameters() : 
        param.requires_grad = False
        if name[0] == '7' or name[0] == '8':
            param.requires_grad = True
        
    optimizer = torch.optim.Adam(net.parameters(), lr = hyper_params["learning_rate"])
    total_step = len(data.train_ds) // hyper_params["batch_size"]
    train_loss_list = list()
    val_loss_list = list()
    min_val = 0
    savename = '../saved_models/smallest_classifier/model' + str(repeated) + '.pt'
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
    #         torch.nn.utils.clip_grad_value_(net.parameters(), 10)
            optimizer.step()

            if i % 50 == 49 :
                print('epoch = ', epoch, ' step = ', i + 1, ' of total steps ', total_step, ' loss = ', loss.item())

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

        print('epoch : ', epoch + 1, ' / ', hyper_params["num_epochs"], ' | TL : ', train_loss, ' | VL : ', val_loss, ' | VA : ', val_acc * 100)

        if (val_acc * 100) > min_val :
            print('saving model')
            min_val = val_acc * 100
            torch.save(net.state_dict(), savename)