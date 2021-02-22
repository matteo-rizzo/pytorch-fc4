import os
import time

import torch
from torch.utils.data import DataLoader

from auxiliary.settings import DEVICE
from auxiliary.utils import print_metrics, log_metrics
from classes.data.ColorCheckerDataset import ColorCheckerDataset
from classes.fc4.ModelFC4 import ModelFC4
from classes.training.Evaluator import Evaluator
from classes.training.LossTracker import LossTracker

EPOCHS = 2000
BATCH_SIZE = 1
LEARNING_RATE = 0.0003
FOLD_NUM = 0
TRAIN_VIS_IMG = "8D5U5549.png"
TEST_VIS_IMG = "IMG_0753.png"

RELOAD_CHECKPOINT = False
PATH_TO_PTH_CHECKPOINT = os.path.join("trained_models", "fold_{}".format(FOLD_NUM), "model.pth")


def main():
    path_to_log = os.path.join("logs", "fold_{}_{}".format(str(FOLD_NUM), str(time.time())))
    os.makedirs(path_to_log, exist_ok=True)
    path_to_metrics_log = os.path.join(path_to_log, "metrics.csv")

    model = ModelFC4()

    if RELOAD_CHECKPOINT:
        print('\n Reloading checkpoint - pretrained model stored at: {} \n'.format(PATH_TO_PTH_CHECKPOINT))
        model.load(PATH_TO_PTH_CHECKPOINT)

    model.print_network()
    model.log_network(path_to_log)
    model.set_optimizer(LEARNING_RATE)

    training_set = ColorCheckerDataset(train=True, folds_num=FOLD_NUM)
    training_loader = DataLoader(training_set, batch_size=BATCH_SIZE, shuffle=True, num_workers=20, drop_last=True)
    print("\n Training set size ... : {}".format(len(training_set)))

    test_set = ColorCheckerDataset(train=False, folds_num=FOLD_NUM)
    test_loader = DataLoader(test_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=20, drop_last=True)
    print(" Test set size ....... : {}\n".format(len(test_set)))

    path_to_train_vis = os.path.join(path_to_log, "train_vis_{}".format(TRAIN_VIS_IMG))
    if TRAIN_VIS_IMG:
        print("Training vis for monitored image {} will be saved at {}".format(TRAIN_VIS_IMG, path_to_train_vis))
        os.makedirs(path_to_train_vis)

    path_to_test_vis = os.path.join(path_to_log, "test_vis_{}".format(TEST_VIS_IMG))
    if TRAIN_VIS_IMG:
        print("Test vis for monitored image {} will be saved at {}\n".format(TEST_VIS_IMG, path_to_test_vis))
        os.makedirs(path_to_test_vis)

    print("\n**************************************************************")
    print("\t\t\t Training FC4 - Fold {}".format(FOLD_NUM))
    print("**************************************************************\n")

    evaluator = Evaluator()
    best_val_loss, best_metrics = 100.0, evaluator.get_best_metrics()
    train_loss, val_loss = LossTracker(), LossTracker()

    for epoch in range(EPOCHS):

        # --- Training ---

        model.train_mode()
        train_loss.reset()
        start = time.time()

        for i, data in enumerate(training_loader):
            model.reset_gradient()
            img, label, file_name = data
            img, label = img.to(DEVICE), label.to(DEVICE)

            path_to_epoch_vis = os.path.join(path_to_train_vis, "epoch_{}.png".format(epoch))
            pred = model.predict(img, vis_conf=file_name[0] == TRAIN_VIS_IMG, path_to_vis=path_to_epoch_vis)

            loss = model.optimize(pred, label)
            train_loss.update(loss)

            if i % 5 == 0:
                print("[ Epoch: {}/{} - Batch: {} ] | [ Train loss: {:.4f} ]".format(epoch, EPOCHS, i, loss))

        train_time = time.time() - start

        # --- Validation ---

        start = time.time()

        val_loss.reset()

        if epoch % 5 == 0:
            evaluator.reset_errors()
            model.evaluation_mode()

            print("\n--------------------------------------------------------------")
            print("\t\t\t Validation")
            print("--------------------------------------------------------------\n")

            with torch.no_grad():
                for i, data in enumerate(test_loader):
                    img, label, file_name = data
                    img, label = img.to(DEVICE), label.to(DEVICE)

                    path_to_epoch_vis = os.path.join(path_to_test_vis, "epoch_{}.png".format(epoch))
                    o = model.predict(img, vis_conf=file_name[0] == TEST_VIS_IMG, path_to_vis=path_to_epoch_vis)

                    loss = model.get_angular_loss(o, label).item()
                    val_loss.update(loss)
                    evaluator.add_error(loss)

                    if i % 5 == 0:
                        print("[ Epoch: {}/{} - Batch: {}] | Val loss: {:.4f} ]".format(epoch, EPOCHS, i, loss))

            print("\n--------------------------------------------------------------\n")

        val_time = time.time() - start

        metrics = evaluator.compute_metrics()
        print("\n********************************************************************")
        print(" Train Time ... : {:.4f}".format(train_time))
        print(" Train Loss ... : {:.4f}".format(train_loss.avg))
        if val_time > 0.1:
            print("....................................................................")
            print(" Val Time ..... : {:.4f}".format(val_time))
            print(" Val Loss ..... : {:.4f}".format(val_loss.avg))
            print("....................................................................")
            print_metrics(metrics, best_metrics)
        print("********************************************************************\n")

        if 0 < val_loss.avg < best_val_loss:
            best_val_loss = val_loss.avg
            best_metrics = evaluator.update_best_metrics()
            print("Saving new best model... \n")
            model.save(os.path.join(path_to_log, "model.pth"))

        log_metrics(train_loss.avg, val_loss.avg, metrics, best_metrics, path_to_metrics_log)


if __name__ == '__main__':
    main()
