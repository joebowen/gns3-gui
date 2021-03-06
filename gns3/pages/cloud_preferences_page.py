# -*- coding: utf-8 -*-
from ..ui.cloud_preferences_page_ui import Ui_CloudPreferencesPageWidget
from ..settings import CLOUD_SETTINGS
from ..utils.choices_spinbox import ChoicesSpinBox

from PyQt4 import QtGui
from PyQt4 import Qt

import importlib
from unittest import mock


# mock api cloud interface until cloud.py module is merged
RackspaceCtrl = mock.MagicMock()
RackspaceCtrl.return_value = RackspaceCtrl
RackspaceCtrl.list_regions.return_value = ['United States', 'Ireland']
FAKE_PROVIDERS = {
    "rackspace": ("Rackspace", 'gns3.pages.cloud_preferences_page.RackspaceCtrl'),
}

# TODO move this to provider ctrl?
RACKSPACE_RAM_CHOICES = [1, 2, 4, 8, 15, 30, 60, 90, 120]


def import_from_string(string_val):
    """
    Attempt to import a class from a string representation.
    """
    try:
        parts = string_val.split('.')
        module_path, class_name = '.'.join(parts[:-1]), parts[-1]
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except ImportError:
        msg = "Could not import '%s'." % string_val
        raise ImportError(msg)


class CloudPreferencesPage(QtGui.QWidget, Ui_CloudPreferencesPageWidget):
    """
    QWidget configuration page for cloud preferences.
    """
    def __init__(self):

        QtGui.QWidget.__init__(self)
        self.setupUi(self)

        # the list containing provider controller classes
        self.provider_controllers = {}
        # map region ids to combobox indexes
        self.region_index_id = []
        # map provider ids to combobox indexes
        self.provider_index_id = []

        # insert Terms&Condition link inside the checkbox
        self.uiTermsLabel.setText('Accept <a href="{}">Terms and Conditions</a>'.format('#'))

        # custom spinboxes
        self.uiMemPerInstanceSpinBox = ChoicesSpinBox(choices=RACKSPACE_RAM_CHOICES, parent=self)
        self.uiStartNewProjectLayout.insertWidget(2, self.uiMemPerInstanceSpinBox)
        self.uiMemPerNewInstanceSpinBox = ChoicesSpinBox(choices=RACKSPACE_RAM_CHOICES, parent=self)
        self.uiNewInstancesLayout.insertWidget(0, self.uiMemPerNewInstanceSpinBox)

        from ..main_window import MainWindow
        self.settings = MainWindow.instance().cloud_settings()

    def _get_region_index(self, region_id):
        try:
            return self.region_index_id.index(region_id)
        except ValueError:
            return -1

    def _store_api_key(self):
        """
        helper method, returns whether user wants to store api keys or not
        """
        return self.uiRememberAPIKeyRadioButton.isChecked()

    def _terms_accepted(self):
        return self.uiTermsCheckBox.checkState() == Qt.Qt.Checked

    def _validate(self):
        """
        Check if settings are ok
        """
        errors = ""
        can_authenticate = self.uiUserNameLineEdit.text() and self.uiAPIKeyLineEdit.text()
        remember_have_been_set = self.uiRememberAPIKeyRadioButton.isChecked() or \
            self.uiForgetAPIKeyRadioButton.isChecked()

        if can_authenticate and not remember_have_been_set:
            errors += "Please choose if you want to persist your API keys or not.\n"

        if can_authenticate and not self._terms_accepted():
            errors += "You have to accept Terms and Conditions to proceed.\n"

        if errors:
            QtGui.QMessageBox.critical(self, "Cloud Preferences", errors)
            return False
        return True

    def loadPreferences(self):
        """
        Load cloud preferences and populate the panel
        """
        self.provider_controllers.clear()

        # fill provider combobox
        self.provider_index_id = [""]
        self.uiCloudProviderComboBox.addItem("Select provider...")
        for k, v in FAKE_PROVIDERS.items():
            self.uiCloudProviderComboBox.addItem(v[0])
            self.provider_controllers[k] = import_from_string(v[1])
            self.provider_index_id.append(k)

        # do not select anything the very first time this page is loaded
        if not self.settings['cloud_store_api_key_chosen']:
            return

        username = self.settings['cloud_user_name']
        apikey = self.settings['cloud_api_key']
        provider_id = self.settings['cloud_provider']
        region = self.settings['cloud_region']

        # instance a provider controller and try to use it
        try:
            provider = self.provider_controllers[provider_id]()
            if provider.authenticate():
                # fill region combo box
                self.region_index_id = [""]
                self.uiRegionComboBox.addItem("Select region...")
                for r in provider.list_regions():
                    self.uiRegionComboBox.addItem(r)
                    self.region_index_id.append(r)
        except KeyError:
            # username/apikey are not set
            pass

        # populate all the cloud stuff
        self.uiUserNameLineEdit.setText(username)
        self.uiAPIKeyLineEdit.setText(apikey)
        self.uiCloudProviderComboBox.setCurrentIndex(self.provider_index_id.index(provider_id))
        self.uiRegionComboBox.setCurrentIndex(self._get_region_index(region))
        if self.settings.get("cloud_store_api_key"):
            self.uiRememberAPIKeyRadioButton.setChecked(True)
        else:
            self.uiForgetAPIKeyRadioButton.setChecked(True)
        self.uiNumOfInstancesSpinBox.setValue(self.settings['instances_per_project'])
        self.uiMemPerInstanceSpinBox.setValue(self.settings['memory_per_instance'])
        self.uiMemPerNewInstanceSpinBox.setValue(self.settings['memory_per_new_instance'])
        self.uiTermsCheckBox.setChecked(self.settings['accepted_terms'])
        self.uiTimeoutSpinBox.setValue(self.settings['instance_timeout'])

    def savePreferences(self):
        """
        Save cloud preferences
        """
        if self._validate():
            self.settings['cloud_user_name'] = self.uiUserNameLineEdit.text()
            self.settings['cloud_api_key'] = self.uiAPIKeyLineEdit.text()
            self.settings['cloud_store_api_key'] = True
            if self.uiCloudProviderComboBox.currentIndex() >= 0:
                self.settings['cloud_provider'] = \
                    self.provider_index_id[self.uiCloudProviderComboBox.currentIndex()]
            if self.uiRegionComboBox.currentIndex() >= 0:
                self.settings['cloud_region'] = \
                    self.region_index_id[self.uiRegionComboBox.currentIndex()]
            self.settings['instances_per_project'] = self.uiNumOfInstancesSpinBox.value()
            self.settings['memory_per_instance'] = self.uiMemPerInstanceSpinBox.value()
            self.settings['memory_per_new_instance'] = self.uiMemPerNewInstanceSpinBox.value()
            self.settings['accepted_terms'] = self.uiTermsCheckBox.isChecked()
            self.settings['instance_timeout'] = self.uiTimeoutSpinBox.value()

            if not self.settings['cloud_store_api_key_chosen']:
                # user made a choice at this point
                self.settings['cloud_store_api_key_chosen'] = True

            from ..main_window import MainWindow
            MainWindow.instance().setCloudSettings(self.settings, persist=self._store_api_key())

            return True
        return False
